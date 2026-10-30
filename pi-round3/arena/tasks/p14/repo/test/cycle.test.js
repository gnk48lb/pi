'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { cycleStarts, cycleBounds } = require('../src');

test('cycleStarts lists consecutive monthly starts', () => {
  assert.deepStrictEqual(cycleStarts(15, '2025-01-15', 4), ['2025-01-15', '2025-02-15', '2025-03-15', '2025-04-15']);
});

test('cycleBounds of a date in the middle of a month', () => {
  assert.deepStrictEqual(cycleBounds(1, '2025-01-17'), { start: '2025-01-01', next: '2025-02-01', days: 31 });
});

test('cycleBounds of a date before the anchor day belongs to the previous month\'s cycle', () => {
  assert.deepStrictEqual(cycleBounds(10, '2025-01-05'), { start: '2024-12-10', next: '2025-01-10', days: 31 });
});
