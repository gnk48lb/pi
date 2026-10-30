'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { parseCsv } = require('../src/csv');

test('rows are keyed by the header names and numbered from 2', () => {
  const rows = parseCsv('a,b\n1,2\n3,4\n');
  assert.equal(rows.length, 2);
  assert.equal(rows[0].a, '1');
  assert.equal(rows[1].b, '4');
  assert.deepEqual(rows.map((row) => row._row), [2, 3]);
});

test('the last line does not need a newline', () => {
  assert.equal(parseCsv('a,b\n1,2').length, 1);
});

test('blank lines are ignored', () => {
  assert.equal(parseCsv('a,b\n\n1,2\n\n').length, 1);
});

test('a header only file has no rows', () => {
  assert.deepEqual(parseCsv('a,b\n'), []);
});
