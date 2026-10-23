'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { fresh, ok } = require('./helpers');

test('first page has ten books and there are two pages', () => {
  const app = fresh();
  const page = ok(app.handle('GET', '/books'));
  assert.equal(page.items.length, 10);
  assert.equal(page.total, 12);
  assert.equal(page.totalPages, 2);
  assert.equal(page.items[0].title, 'The Salt Road');
});

test('second page has the remaining two books', () => {
  const app = fresh();
  const page = ok(app.handle('GET', '/books', { query: { page: '2' } }));
  assert.deepEqual(page.items.map((b) => b.title), ['Winter Ledger', 'Cold Arithmetic']);
});

test('filter by author and sort by price descending', () => {
  const app = fresh();
  const page = ok(app.handle('GET', '/books', { query: { author: '2', sort: '-price' } }));
  assert.deepEqual(page.items.map((b) => b.title), ['Small Engines', 'Tidewater', 'Night Ferry']);
});

test('filter by tag', () => {
  const app = fresh();
  const page = ok(app.handle('GET', '/books', { query: { tag: 'mystery', sort: 'title' } }));
  assert.deepEqual(page.items.map((b) => b.title), ['Hollow Hours', 'Night Ferry']);
});

test('unknown book is a 404', () => {
  const app = fresh();
  assert.equal(app.handle('GET', '/books/999').status, 404);
});

test('creating a book returns 201 and defaults the tags', () => {
  const app = fresh();
  const created = ok(app.handle('POST', '/books', { body: { title: 'New Title', authorId: 3, price: 5 } }), 201);
  assert.equal(created.id, 13);
  assert.deepEqual(created.tags, []);
  assert.equal(ok(app.handle('GET', '/books/13')).title, 'New Title');
});

test('creating an invalid book is a 422', () => {
  const app = fresh();
  assert.equal(app.handle('POST', '/books', { body: { title: '', authorId: 3, price: 5 } }).status, 422);
  assert.equal(app.handle('POST', '/books', { body: { title: 'x', authorId: 99, price: 5 } }).status, 422);
});

test('patching a book changes and keeps its price', () => {
  const app = fresh();
  ok(app.handle('PATCH', '/books/1', { body: { price: 15 } }));
  assert.equal(ok(app.handle('GET', '/books/1')).price, 15);
});

test('an invalid patch is rejected and leaves the book unchanged', () => {
  const app = fresh();
  const before = JSON.parse(JSON.stringify(ok(app.handle('GET', '/books/2'))));
  assert.equal(app.handle('PATCH', '/books/2', { body: { price: -5, title: 'Changed' } }).status, 422);
  assert.deepEqual(ok(app.handle('GET', '/books/2')), before);
});

test('changing a response body does not change the stored book', () => {
  const app = fresh();
  const body = ok(app.handle('GET', '/books/1'));
  body.title = 'Hacked';
  body.tags.push('hacked');
  const again = ok(app.handle('GET', '/books/1'));
  assert.equal(again.title, 'The Salt Road');
  assert.deepEqual(again.tags, ['travel', 'history']);
});

test('changing the request body after creating a book does not change the stored book', () => {
  const app = fresh();
  const body = { title: 'Shared', authorId: 1, price: 7, tags: ['a'] };
  ok(app.handle('POST', '/books', { body }), 201);
  body.tags.push('b');
  assert.deepEqual(ok(app.handle('GET', '/books/13')).tags, ['a']);
});
