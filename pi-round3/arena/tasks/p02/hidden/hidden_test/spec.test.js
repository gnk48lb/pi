'use strict';
// Hidden acceptance tests for p02 (csvstat --format). Copied into the workspace only after the agent is done.

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.join(__dirname, '..');
const bin = path.join(root, 'bin', 'csvstat.js');
const wide = path.join(__dirname, 'fixtures', 'wide.csv');
const sample = path.join(__dirname, 'fixtures', 'sample.csv');

function run(...args) {
  return spawnSync(process.execPath, [bin, ...args], { encoding: 'utf8', cwd: root });
}

const WIDE_TEXT = [
  'id: count=4 min=1 max=4 mean=2.5 sum=10',
  'temperature_c: count=3 min=-3.25 max=12 mean=5.4167 sum=16.25',
  'humidity: count=3 min=40 max=61 mean=52.1667 sum=156.5',
  '',
].join('\n');

const WIDE_TABLE = [
  'column        | count | min   | max | mean    | sum',
  '--------------|-------|-------|-----|---------|------',
  'id            | 4     | 1     | 4   | 2.5     | 10',
  'temperature_c | 3     | -3.25 | 12  | 5.4167  | 16.25',
  'humidity      | 3     | 40    | 61  | 52.1667 | 156.5',
  '',
].join('\n');

const WIDE_JSON = {
  columns: {
    id: { count: 4, min: 1, max: 4, mean: 2.5, sum: 10 },
    temperature_c: { count: 3, min: -3.25, max: 12, mean: 5.4167, sum: 16.25 },
    humidity: { count: 3, min: 40, max: 61, mean: 52.1667, sum: 156.5 },
  },
};

const SAMPLE_TEXT = [
  'price: count=3 min=1.5 max=4 mean=2.6667 sum=8',
  'qty: count=3 min=1 max=10 mean=4.3333 sum=13',
  '',
].join('\n');

const SAMPLE_TABLE = [
  'column | count | min | max | mean   | sum',
  '-------|-------|-----|-----|--------|----',
  'price  | 3     | 1.5 | 4   | 2.6667 | 8',
  'qty    | 3     | 1   | 10  | 4.3333 | 13',
  '',
].join('\n');

const SAMPLE_JSON = {
  columns: {
    price: { count: 3, min: 1.5, max: 4, mean: 2.6667, sum: 8 },
    qty: { count: 3, min: 1, max: 10, mean: 4.3333, sum: 13 },
  },
};

const pretty = (obj) => JSON.stringify(obj, null, 2) + '\n';

test('default output is still the text format', () => {
  for (const [file, expected] of [[wide, WIDE_TEXT], [sample, SAMPLE_TEXT]]) {
    const r = run(file);
    assert.equal(r.status, 0);
    assert.equal(r.stdout, expected);
  }
});

test('--format text is identical to the default', () => {
  assert.equal(run(wide, '--format', 'text').stdout, WIDE_TEXT);
  assert.equal(run(sample, '--format=text').stdout, SAMPLE_TEXT);
});

test('--format json prints the documented document', () => {
  for (const [file, expected] of [[wide, WIDE_JSON], [sample, SAMPLE_JSON]]) {
    const r = run(file, '--format', 'json');
    assert.equal(r.status, 0, r.stderr);
    assert.equal(r.stdout, pretty(expected));
  }
});

test('--format table prints the documented table', () => {
  assert.equal(run(wide, '--format', 'table').stdout, WIDE_TABLE);
  assert.equal(run(sample, '--format', 'table').stdout, SAMPLE_TABLE);
});

test('--format=value spelling works', () => {
  assert.equal(run(wide, '--format=json').stdout, pretty(WIDE_JSON));
  assert.equal(run(sample, '--format=table').stdout, SAMPLE_TABLE);
});

test('the option may come before the file', () => {
  assert.equal(run('--format', 'table', sample).stdout, SAMPLE_TABLE);
  assert.equal(run('--format=json', sample).stdout, pretty(SAMPLE_JSON));
});

test('--columns combines with --format and keeps file order', () => {
  const r = run(wide, '--columns', 'humidity,id', '--format', 'json');
  assert.equal(r.status, 0, r.stderr);
  const doc = JSON.parse(r.stdout);
  assert.deepEqual(Object.keys(doc.columns), ['id', 'humidity']);
  assert.equal(r.stdout, pretty({ columns: { id: WIDE_JSON.columns.id, humidity: WIDE_JSON.columns.humidity } }));

  const t = run(sample, '--columns=qty', '--format=table');
  assert.equal(
    t.stdout,
    [
      'column | count | min | max | mean   | sum',
      '-------|-------|-----|-----|--------|----',
      'qty    | 3     | 1   | 10  | 4.3333 | 13',
      '',
    ].join('\n')
  );
});

test('an unknown format is a usage error', () => {
  const r = run(sample, '--format', 'xml');
  assert.equal(r.status, 2);
  assert.equal(r.stdout, '');
  assert.match(r.stderr, /xml/);
});

test('existing error handling still works', () => {
  const r = run(sample, '--columns', 'nope', '--format', 'json');
  assert.equal(r.status, 2);
  assert.match(r.stderr, /unknown column "nope"/);
  assert.equal(run(path.join(__dirname, 'fixtures', 'missing.csv'), '--format', 'json').status, 1);
});

test('README documents --format', () => {
  const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
  assert.match(readme, /--format/);
});

test('new tests were added in test/format.test.js', () => {
  const file = path.join(root, 'test', 'format.test.js');
  assert.ok(fs.existsSync(file), 'test/format.test.js is missing');
  const src = fs.readFileSync(file, 'utf8');
  const count = (src.match(/^\s*(?:test|it)\s*\(/gm) || []).length;
  assert.ok(count >= 3, `expected at least 3 tests in test/format.test.js, found ${count}`);
});
