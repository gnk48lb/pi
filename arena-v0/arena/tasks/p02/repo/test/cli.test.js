'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.join(__dirname, '..');
const bin = path.join(root, 'bin', 'csvstat.js');
const sample = path.join(root, 'data', 'sample.csv');

function run(...args) {
  return spawnSync(process.execPath, [bin, ...args], { encoding: 'utf8' });
}

test('prints stats for numeric columns', () => {
  const r = run(sample);
  assert.equal(r.status, 0);
  assert.equal(
    r.stdout,
    'price: count=3 min=1.5 max=4 mean=2.6667 sum=8\n' + 'qty: count=3 min=1 max=10 mean=4.3333 sum=13\n'
  );
});

test('--columns restricts the output (both spellings)', () => {
  const expected = 'qty: count=3 min=1 max=10 mean=4.3333 sum=13\n';
  assert.equal(run(sample, '--columns', 'qty').stdout, expected);
  assert.equal(run(sample, '--columns=qty').stdout, expected);
});

test('unknown column is a usage error', () => {
  const r = run(sample, '--columns', 'nope');
  assert.equal(r.status, 2);
  assert.match(r.stderr, /unknown column "nope"/);
});

test('missing file exits with 1', () => {
  const r = run(path.join(root, 'data', 'missing.csv'));
  assert.equal(r.status, 1);
});
