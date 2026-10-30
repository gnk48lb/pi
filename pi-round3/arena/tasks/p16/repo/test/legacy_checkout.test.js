'use strict';
// Contract from the 2019 reseller agreement, kept as a regression test: a basket of exactly 50.00 still pays shipping.
const test = require('node:test');
const assert = require('node:assert/strict');
const { orderTotal } = require('../src');

test('legacy: a 50.00 basket pays the flat shipping fee', () => {
  const order = { lines: [{ unitCents: 2500, qty: 2 }], country: 'DE' };
  assert.strictEqual(orderTotal(order).shipping, 499);
});
