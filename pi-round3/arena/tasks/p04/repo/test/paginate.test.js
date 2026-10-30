'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { paginate } = require('../src/util/paginate');

const items = Array.from({ length: 25 }, (_, i) => i + 1);

test('first page', () => {
  const p = paginate(items, 1, 10);
  assert.deepEqual(p.items, items.slice(0, 10));
  assert.equal(p.totalPages, 3);
});

test('last page is short', () => {
  assert.deepEqual(paginate(items, 3, 10).items, [21, 22, 23, 24, 25]);
});

test('an empty list still has one page', () => {
  const p = paginate([], 1, 10);
  assert.equal(p.totalPages, 1);
  assert.deepEqual(p.items, []);
});
