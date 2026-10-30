'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { fresh, ok } = require('./helpers');

const order = { customerId: 'c-1', lines: [{ bookId: 1, qty: 2 }, { bookId: 2, qty: 1 }] };

test('an order is priced from the books', () => {
  const app = fresh();
  const created = ok(app.handle('POST', '/orders', { body: order }), 201);
  assert.equal(created.total, 34.99);
  assert.deepEqual(created.lines.map((l) => l.title), ['The Salt Road', 'Lanterns']);
});

test('an order can be fetched again', () => {
  const app = fresh();
  const created = ok(app.handle('POST', '/orders', { body: order }), 201);
  assert.deepEqual(ok(app.handle('GET', `/orders/${created.id}`)), created);
});

test('an unknown book in an order is a 422', () => {
  const app = fresh();
  const res = app.handle('POST', '/orders', { body: { customerId: 'c-1', lines: [{ bookId: 99, qty: 1 }] } });
  assert.equal(res.status, 422);
});

test('quantities must be positive integers', () => {
  const app = fresh();
  const res = app.handle('POST', '/orders', { body: { customerId: 'c-1', lines: [{ bookId: 1, qty: 0 }] } });
  assert.equal(res.status, 422);
});

test('an order keeps the prices that were valid when it was placed', () => {
  const app = fresh();
  const created = ok(app.handle('POST', '/orders', { body: order }), 201);
  ok(app.handle('PATCH', '/books/1', { body: { price: 100 } }));
  const again = ok(app.handle('GET', `/orders/${created.id}`));
  assert.equal(again.total, 34.99);
  assert.equal(again.lines[0].price, 12.5);
});
