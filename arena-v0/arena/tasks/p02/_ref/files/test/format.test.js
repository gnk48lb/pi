'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { formatJson, formatTable } = require('../src/format');

const stats = [
  { name: 'price', count: 3, min: 1.5, max: 4, mean: 8 / 3, sum: 8 },
  { name: 'qty', count: 3, min: 1, max: 10, mean: 13 / 3, sum: 13 },
];

test('formatJson rounds and keeps column order', () => {
  const doc = JSON.parse(formatJson(stats));
  assert.deepEqual(Object.keys(doc.columns), ['price', 'qty']);
  assert.deepEqual(doc.columns.price, { count: 3, min: 1.5, max: 4, mean: 2.6667, sum: 8 });
});

test('formatTable pads cells to the widest value', () => {
  assert.equal(
    formatTable(stats),
    [
      'column | count | min | max | mean   | sum',
      '-------|-------|-----|-----|--------|----',
      'price  | 3     | 1.5 | 4   | 2.6667 | 8',
      'qty    | 3     | 1   | 10  | 4.3333 | 13',
      '',
    ].join('\n')
  );
});

test('the CLI accepts --format in both spellings and rejects unknown values', () => {
  const bin = path.join(__dirname, '..', 'bin', 'csvstat.js');
  const sample = path.join(__dirname, '..', 'data', 'sample.csv');
  const run = (...args) => spawnSync(process.execPath, [bin, sample, ...args], { encoding: 'utf8' });
  assert.equal(run('--format', 'json').stdout, run('--format=json').stdout);
  assert.equal(run('--format', 'text').stdout, run().stdout);
  const bad = run('--format', 'xml');
  assert.equal(bad.status, 2);
  assert.match(bad.stderr, /unknown format "xml"/);
});
