'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { main } = require('../src/cli');

const DATA = path.join(__dirname, '..', 'data');

function run(args) {
  let stdout = '';
  let stderr = '';
  const status = main(args, { write: (s) => { stdout += s; } }, { write: (s) => { stderr += s; } });
  return { status, stdout, stderr };
}

test('report for a simple file', () => {
  const { status, stdout, stderr } = run(['report', path.join(DATA, 'feb.csv')]);
  assert.equal(status, 0);
  assert.equal(stderr, '');
  assert.deepEqual(stdout.trimEnd().split('\n').map((line) => line.trim().split(/\s+/)), [
    ['Food', '51.80'], ['Office', '12.40'], ['Software', '99.00'], ['Travel', '101.00'], ['TOTAL', '264.20'],
  ]);
});

test('--month keeps only that month', () => {
  const { stdout } = run(['report', path.join(DATA, 'feb.csv'), '--month', '2026-03']);
  assert.equal(stdout.trim().split(/\s+/).join(' '), 'TOTAL 0.00');
});

test('an unknown currency is reported with its row and exit status 2', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'spendsum-'));
  const file = path.join(dir, 'bad.csv');
  fs.writeFileSync(file, 'date,category,note,amount,currency\n2026-01-01,Food,x,5.00,USD\n2026-01-02,Food,y,5.00,XYZ\n');
  const { status, stdout, stderr } = run(['report', file]);
  fs.rmSync(dir, { recursive: true, force: true });
  assert.equal(status, 2);
  assert.equal(stdout, '');
  assert.equal(stderr, 'spendsum: line 3: unknown currency "XYZ"\n');
});

test('usage error', () => {
  assert.equal(run([]).status, 2);
});
