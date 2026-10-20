'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { numericColumns, summarize } = require('../src/stats');
const { fmtNum, formatText } = require('../src/format');

const table = {
  header: ['name', 'x', 'y'],
  rows: [
    ['a', '1', ''],
    ['b', '2.5', '7'],
    ['c', '', '8'],
  ],
};

test('numericColumns skips text columns and empty cells', () => {
  assert.deepEqual(numericColumns(table, null), [
    { name: 'x', values: [1, 2.5] },
    { name: 'y', values: [7, 8] },
  ]);
});

test('numericColumns can be restricted by name', () => {
  assert.deepEqual(numericColumns(table, ['y']), [{ name: 'y', values: [7, 8] }]);
});

test('summarize', () => {
  assert.deepEqual(summarize([1, 2.5]), { count: 2, min: 1, max: 2.5, mean: 1.75, sum: 3.5 });
});

test('fmtNum rounds to 4 decimals and drops trailing zeros', () => {
  assert.equal(fmtNum(8 / 3), '2.6667');
  assert.equal(fmtNum(4), '4');
  assert.equal(fmtNum(2.50004), '2.5');
});

test('formatText prints one line per column', () => {
  const stats = [{ name: 'x', count: 2, min: 1, max: 2.5, mean: 1.75, sum: 3.5 }];
  assert.equal(formatText(stats), 'x: count=2 min=1 max=2.5 mean=1.75 sum=3.5\n');
  assert.equal(formatText([]), 'No numeric columns found\n');
});
