'use strict';
// Hidden acceptance tests of p12 (spendsum reads an Excel-style CSV export).
const test = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const BIN = path.join(ROOT, 'bin', 'spendsum.js');
const BOM = '﻿';

function spend(t, args, files = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'spendsum-spec-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  for (const [name, content] of Object.entries(files)) fs.writeFileSync(path.join(dir, name), content);
  const full = args.map((a) => (a.startsWith('@') ? path.join(dir, a.slice(1)) : a));
  const started = Date.now();
  const r = spawnSync(process.execPath, [BIN, ...full], {
    cwd: dir, encoding: 'utf8', timeout: 60000, maxBuffer: 64 * 1024 * 1024,
  });
  return { status: r.status, stdout: r.stdout, stderr: r.stderr, ms: Date.now() - started };
}

// "Food   218.20" lines -> [['Food', '218.20'], ...]
function table(stdout) {
  return stdout.trimEnd().split('\n').map((line) => {
    const m = /^(.*?)\s{2,}(-?[\d,]+\.\d\d)$/.exec(line.trimEnd());
    assert.ok(m, 'unparsable report line: ' + JSON.stringify(line));
    return [m[1].trim(), m[2]];
  });
}

const MARCH_ROWS = [
  'date,category,note,amount,currency',
  '2026-03-02,Food,Team lunch,48.00,EUR',
  '2026-03-03,Travel,"Train tickets, Berlin","1,200.00",EUR',
  '2026-03-05,Food,"Coffee ""Blue Bottle""",8.20,USD',
  '2026-03-09,Office,"Printer paper\nand toner",86.40,EUR',
  '2026-03-11,Travel,Taxi,32.00,GBP',
  '2026-03-12,Software,"Licence, annual","2,450.00",USD',
  '2026-03-18,Food,Client dinner,120.00,EUR',
  '2026-03-27,Office,Desk lamp,45.60,EUR',
  '2026-04-01,Travel,Flight deposit,300.00,EUR',
];

const MARCH = [['Food', '218.20'], ['Office', '165.00'], ['Software', '2,450.00'], ['Travel', '1,548.00'], ['TOTAL', '4,381.20']];
const MARCH_ALL = [['Food', '218.20'], ['Office', '165.00'], ['Software', '2,450.00'], ['Travel', '1,923.00'], ['TOTAL', '4,756.20']];

// The same export in the different shapes spreadsheet programs write it.
function marchText({ bom, eol, inner, final }) {
  const text = MARCH_ROWS.map((row) => row.replace('\n', inner)).join(eol) + (final ? eol : '');
  return (bom ? BOM : '') + text;
}

test('the shipped March export gives the right report', (t) => {
  const file = path.join(ROOT, 'data', 'march.csv');
  const r = spend(t, ['report', file, '--month', '2026-03']);
  assert.equal(r.stderr, '');
  assert.equal(r.status, 0);
  assert.deepEqual(table(r.stdout), MARCH);
});

test('without --month every row counts', (t) => {
  const r = spend(t, ['report', path.join(ROOT, 'data', 'march.csv')]);
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(table(r.stdout), MARCH_ALL);
});

test('other months', (t) => {
  const file = path.join(ROOT, 'data', 'march.csv');
  assert.deepEqual(table(spend(t, ['report', file, '--month', '2026-04']).stdout), [['Travel', '375.00'], ['TOTAL', '375.00']]);
  assert.deepEqual(table(spend(t, ['report', file, '--month', '2026-05']).stdout), [['TOTAL', '0.00']]);
});

test('the same export in every shape: BOM or not, CRLF or LF, line breaks inside quotes, final newline or not', async (t) => {
  for (const bom of [true, false]) {
    for (const eol of ['\r\n', '\n']) {
      for (const inner of ['\n', '\r\n']) {
        for (const final of [true, false]) {
          const label = JSON.stringify({ bom, eol, inner, final });
          await t.test(label, (st) => {
            const r = spend(st, ['report', '@march.csv', '--month', '2026-03'], { 'march.csv': marchText({ bom, eol, inner, final }) });
            assert.equal(r.stderr, '', label);
            assert.equal(r.status, 0, label);
            assert.deepEqual(table(r.stdout), MARCH, label);
          });
        }
      }
    }
  }
});

test('blank lines at the end of the file are ignored', (t) => {
  const r = spend(t, ['report', '@m.csv', '--month', '2026-03'], { 'm.csv': marchText({ bom: true, eol: '\r\n', inner: '\n', final: true }) + '\r\n\r\n' });
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(table(r.stdout), MARCH);
});

test('quotes: commas, doubled quotes, empty fields, quoted numbers, a quoted last field and no final newline', (t) => {
  const text = [
    'date,category,note,amount,currency',
    '2026-03-01,"Food, drinks","He said ""hi"", twice","10.00",USD',
    '2026-03-02,"Food, drinks",,20.00,USD',
    '2026-03-03,Misc,"""",1.50,"USD"',
    '2026-03-04,"Misc",plain,"2.00","EUR"',
  ].join('\r\n');
  const r = spend(t, ['report', '@q.csv'], { 'q.csv': text });
  assert.equal(r.stderr, '');
  assert.equal(r.status, 0);
  assert.deepEqual(table(r.stdout), [['Food, drinks', '30.00'], ['Misc', '4.00'], ['TOTAL', '34.00']]);
});

test('columns are found by name, in any order', (t) => {
  const text = [
    'currency,"amount",note,date,category',
    'EUR,"1,000.00","a, b",2026-03-02,Travel',
    'USD,5.25,,2026-03-03,Food',
  ].join('\n');
  const r = spend(t, ['report', '@o.csv', '--month', '2026-03'], { 'o.csv': text });
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(table(r.stdout), [['Food', '5.25'], ['Travel', '1,250.00'], ['TOTAL', '1,255.25']]);
});

test('thousands separators', (t) => {
  const text = [
    'date,category,note,amount,currency',
    '2026-03-02,A,x,"1,234,567.89",USD',
    '2026-03-03,A,x,"1,000",USD',
    '2026-03-04,A,x,999,USD',
    '2026-03-05,B,x,"12,345.60",USD',
    '2026-03-06,B,x,1234.5,USD',
  ].join('\n');
  const r = spend(t, ['report', '@t.csv'], { 't.csv': text });
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(table(r.stdout), [['A', '1,236,566.89'], ['B', '13,580.10'], ['TOTAL', '1,250,146.99']]);
});

test('amounts that are not valid are still input errors', (t) => {
  for (const bad of ['"12,5"', '"1,23"', '"1,2345"', '"1,23,456"', 'abc', '""', '"1.2.3"']) {
    const text = ['date,category,note,amount,currency', '2026-03-02,A,x,5.00,USD', '2026-03-03,A,x,' + bad + ',USD'].join('\r\n');
    const r = spend(t, ['report', '@b.csv'], { 'b.csv': text });
    const shown = bad.replace(/^"|"$/g, '');
    assert.equal(r.status, 2, bad + ' -> ' + r.stderr);
    assert.equal(r.stdout, '', bad);
    assert.equal(r.stderr, 'spendsum: line 3: bad amount ' + JSON.stringify(shown) + '\n', bad);
  }
});

test('an unknown currency is reported with the row number, also in an Excel-style file', (t) => {
  const text = BOM + ['date,category,note,amount,currency', '2026-03-02,A,"x, y",5.00,USD', '2026-03-03,A,x,5.00,XYZ', '2026-03-04,A,x,5.00,USD'].join('\r\n') + '\r\n';
  const r = spend(t, ['report', '@u.csv'], { 'u.csv': text });
  assert.equal(r.status, 2);
  assert.equal(r.stdout, '');
  assert.equal(r.stderr, 'spendsum: line 3: unknown currency "XYZ"\n');
});

test('a custom rates file', (t) => {
  const text = ['date,category,note,amount,currency', '2026-03-02,A,x,"1,000.00",EUR', '2026-03-03,A,x,2.00,USD'].join('\r\n');
  const r = spend(t, ['report', '@c.csv', '--rates', '@rates.json'], { 'c.csv': text, 'rates.json': '{"USD": 1, "EUR": 2}' });
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(table(r.stdout), [['A', '2,002.00'], ['TOTAL', '2,002.00']]);
});

test('a big export is read in reasonable time', (t) => {
  const lines = ['date,category,note,amount,currency'];
  for (let i = 0; i < 20000; i++) lines.push(`2026-03-05,Cat ${i % 7},"note, number ${i}",1.00,USD`);
  const r = spend(t, ['report', '@big.csv'], { 'big.csv': BOM + lines.join('\r\n') + '\r\n' });
  assert.equal(r.status, 0, r.stderr);
  const rows = table(r.stdout);
  assert.equal(rows[rows.length - 1][1], '20,000.00');
  assert.ok(r.ms < 20000, 'took ' + r.ms + ' ms');
});
