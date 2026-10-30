'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { orderTotal } = require('../src');

test('a small order: subtotal, flat shipping, tax on both', () => {
  const order = { lines: [{ unitCents: 1000, qty: 2 }], country: 'DE' };
  assert.deepStrictEqual(orderTotal(order), { subtotal: 2000, discount: 0, shipping: 499, tax: 475, total: 2974 });
});

test('a coupon that brings the order under the free-shipping line makes it pay shipping', () => {
  const order = { lines: [{ unitCents: 3000, qty: 2 }], coupon: { type: 'fixed', value: 1500 }, country: 'GB' };
  assert.deepStrictEqual(orderTotal(order), { subtotal: 6000, discount: 1500, shipping: 499, tax: 1000, total: 5999 });
});

test('several lines are added up', () => {
  const order = {
    lines: [{ unitCents: 1250, qty: 4 }, { unitCents: 799, qty: 1 }, { unitCents: 100, qty: 3 }],
    country: 'FR',
  };
  const result = orderTotal(order);
  assert.strictEqual(result.subtotal, 6099);
  assert.strictEqual(result.shipping, 0);
  assert.strictEqual(result.total, 6099 + 1220);
});
