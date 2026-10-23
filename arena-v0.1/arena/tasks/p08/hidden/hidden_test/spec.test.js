'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const ROOT = path.resolve(__dirname, '..');
const BIN = path.join(ROOT, 'bin', 'logsum.js');
const FIX = path.join(__dirname, 'fixtures');
const expected = JSON.parse(fs.readFileSync(path.join(FIX, 'expected.json'), 'utf8'));
const USAGE = 'usage: logsum [--top N] [FILE]';

function run(args, input) {
  return spawnSync(process.execPath, [BIN, ...args], { cwd: ROOT, input, encoding: 'utf8', timeout: 20000 });
}

test('the documented sample output', () => {
  const r = run(['data/sample.log']);
  assert.equal(r.status, 0, r.stderr);
  assert.equal(r.stdout, expected.sample);
  assert.equal(r.stderr, '');
});

test('standard input, with no argument and with "-"', () => {
  const input = fs.readFileSync(path.join(ROOT, 'data', 'sample.log'));
  assert.equal(run([], input).stdout, expected.sample);
  assert.equal(run(['-'], input).stdout, expected.sample);
});

test('CRLF line endings, blank lines, no final newline, half-up rounding of the latency', () => {
  assert.equal(run([path.join(FIX, 'crlf.log')]).stdout, expected['crlf.log'].default);
});

test('ties: paths alphabetical, the first minute wins, a minute includes the day', () => {
  assert.equal(run([path.join(FIX, 'ties.log')]).stdout, expected['ties.log'].default);
});

test('--top N and --top=N, before or after the file name', () => {
  const f = path.join(FIX, 'ties.log');
  assert.equal(run(['--top', '2', f]).stdout, expected['ties.log'].top2);
  assert.equal(run([f, '--top', '2']).stdout, expected['ties.log'].top2);
  assert.equal(run(['--top=10', f]).stdout, expected['ties.log'].top10);
});

test('no valid request at all', () => {
  assert.equal(run([path.join(FIX, 'none.log')]).stdout, expected['none.log'].default);
});

test('nearest-rank percentiles', () => {
  assert.equal(run([path.join(FIX, 'latency.log')]).stdout, expected['latency.log'].default);
});

test('malformed variants are counted, other lines still work', () => {
  assert.equal(run([path.join(FIX, 'mixed.log')]).stdout, expected['mixed.log'].default);
});

test('usage errors exit with 2 and print nothing on stdout', () => {
  const f = path.join(ROOT, 'data', 'sample.log');
  for (const args of [['--bogus', f], [f, f], ['--top', '0', f], ['--top', 'abc', f], ['--top', '-3', f], ['--top']]) {
    const r = run(args, '');
    assert.equal(r.status, 2, JSON.stringify(args));
    assert.equal(r.stdout, '', JSON.stringify(args));
    assert.ok(r.stderr.includes(USAGE), JSON.stringify(args) + ' -> ' + r.stderr);
  }
});

test('an unreadable file exits with 1 and names the file', () => {
  const r = run(['does-not-exist.log']);
  assert.equal(r.status, 1);
  assert.equal(r.stdout, '');
  assert.ok(r.stderr.includes('logsum: cannot read does-not-exist.log'), r.stderr);
});

test('a big log is summarised quickly and correctly', () => {
  let seed = 12345;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  const lines = [];
  let bytes = 0;
  for (let i = 0; i < 60000; i++) {
    const b = Math.floor(rnd() * 5000);
    bytes += b;
    const sec = String(i % 60).padStart(2, '0');
    lines.push(`10.0.${i % 7}.${i % 200} - - [10/Oct/2026:13:${String(i % 50).padStart(2, '0')}:${sec} +0000] "GET /p/${i % 500}?x=${i} HTTP/1.1" ${[200, 200, 404, 500][i % 4]} ${b} 0.${String(i % 900).padStart(3, '0')}`);
  }
  const started = Date.now();
  const r = run([], lines.join('\n') + '\n');
  assert.ok(Date.now() - started < 10000, 'too slow');
  assert.equal(r.status, 0, r.stderr);
  assert.ok(r.stdout.startsWith('requests: 60000 (valid), 0 (malformed)\n'));
  assert.ok(r.stdout.includes(`bytes: ${bytes}\n`));
  assert.ok(r.stdout.includes('status: 2xx=30000 3xx=0 4xx=15000 5xx=15000\n'));
});

test('tests and docs were written', () => {
  const tests = fs.readFileSync(path.join(ROOT, 'test', 'logsum.test.js'), 'utf8');
  assert.ok((tests.match(/\b(test|it)\(/g) || []).length >= 3, 'test/logsum.test.js needs at least 3 tests');
  const readme = fs.readFileSync(path.join(ROOT, 'README.md'), 'utf8');
  assert.ok(/logsum/.test(readme) && /--top/.test(readme), 'README.md should document the tool and --top');
});
