'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { parseListQuery } = require('../src/util/query');

test('defaults', () => {
  assert.deepEqual(parseListQuery({}), { author: undefined, tag: undefined, sort: undefined, page: 1, perPage: 10 });
});

test('numbers are parsed and bounded', () => {
  const q = parseListQuery({ page: '3', per_page: '500', author: '2' });
  assert.equal(q.page, 3);
  assert.equal(q.perPage, 50);
  assert.equal(q.author, 2);
});

test('garbage falls back to the defaults', () => {
  const q = parseListQuery({ page: 'abc', per_page: '-1', sort: 'rating' });
  assert.equal(q.page, 1);
  assert.equal(q.perPage, 10);
  assert.equal(q.sort, undefined);
});
