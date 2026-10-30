'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { discount } = require('../src');

test('no coupon, no discount', () => {
  assert.strictEqual(discount(2000, undefined), 0);
});

test('a percentage coupon takes that share of the subtotal', () => {
  assert.strictEqual(discount(2000, { type: 'percent', value: 10 }), 200);
});

test('a percentage coupon rounds half up', () => {
  assert.strictEqual(discount(1999, { type: 'percent', value: 15 }), 300);
});

test('a fixed coupon takes its value', () => {
  assert.strictEqual(discount(2000, { type: 'fixed', value: 500 }), 500);
});

test('a fixed coupon never exceeds the subtotal', () => {
  assert.strictEqual(discount(300, { type: 'fixed', value: 500 }), 300);
});

test('an unknown coupon type is an error', () => {
  assert.throws(() => discount(2000, { type: 'bogus', value: 1 }), /unknown coupon type: bogus/);
});
