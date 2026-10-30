'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { prorate } = require('../src');

const april = { start: '2025-04-01', next: '2025-05-01', days: 30 };
const january = { start: '2025-01-01', next: '2025-02-01', days: 31 };

test('an upgrade on the first day of a cycle pays the whole price difference', () => {
  assert.strictEqual(prorate(1000, 2500, '2025-04-01', april), 1500);
});

test('an upgrade in a 31-day cycle is prorated over 31 days', () => {
  assert.strictEqual(prorate(1000, 2500, '2025-01-16', january), 774);
});

test('a downgrade charges nothing', () => {
  assert.strictEqual(prorate(2500, 1000, '2025-01-10', january), 0);
});

test('an unchanged price charges nothing', () => {
  assert.strictEqual(prorate(2500, 2500, '2025-01-10', january), 0);
});
