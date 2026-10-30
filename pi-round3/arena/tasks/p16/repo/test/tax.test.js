'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { taxFor } = require('../src');

test('German VAT is 19%', () => {
  assert.strictEqual(taxFor(10000, 'DE'), 1900);
});

test('tax rounds half up', () => {
  assert.strictEqual(taxFor(50, 'NL'), 11);
  assert.strictEqual(taxFor(1003, 'FR'), 201);
});

test('an unknown country is an error', () => {
  assert.throws(() => taxFor(1000, 'XX'), /unknown country: XX/);
});
