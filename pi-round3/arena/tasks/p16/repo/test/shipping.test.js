'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { shippingFee } = require('../src');

test('small orders pay the flat fee', () => {
  assert.strictEqual(shippingFee(4999), 499);
});

test('big orders ship free', () => {
  assert.strictEqual(shippingFee(5001), 0);
});

test('an order of exactly 50.00 ships free', () => {
  assert.strictEqual(shippingFee(5000), 0);
});
