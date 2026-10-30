'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const ROOT = path.resolve(__dirname, '..');
const run = (args, input) => spawnSync(process.execPath, [path.join(ROOT, 'bin', 'logsum.js'), ...args], { cwd: ROOT, input, encoding: 'utf8' });

const line = (target, status, bytes, secs, minute = '13:55') =>
  `10.0.0.1 - - [10/Oct/2026:${minute}:00 +0000] "GET ${target} HTTP/1.1" ${status} ${bytes} ${secs}\n`;

test('summarises the sample log', () => {
  const r = run(['data/sample.log']);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /^requests: 8 \(valid\), 1 \(malformed\)\nbytes: 9991\n/);
  assert.match(r.stdout, /busiest minute: 10\/Oct\/2026:13:55 \(3 requests\)\n$/);
});

test('reads standard input and strips query strings', () => {
  const r = run([], line('/a?x=1', 200, 10, '0.001') + line('/a?x=2', 200, 20, '0.002'));
  assert.match(r.stdout, /top paths:\n {2}\/a 2\n/);
  assert.match(r.stdout, /bytes: 30\n/);
});

test('no valid requests', () => {
  assert.equal(run([], 'nonsense\n').stdout, 'requests: 0 (valid), 1 (malformed)\nno valid requests\n');
});

test('usage errors exit with 2', () => {
  assert.equal(run(['--top', '0']).status, 2);
  assert.equal(run(['--nope']).status, 2);
});
