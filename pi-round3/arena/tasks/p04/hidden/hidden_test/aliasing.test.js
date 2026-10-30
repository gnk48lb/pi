'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { createDb, createSeededApp } = require('../src');

const ok = (res, status = 200) => {
  assert.equal(res.status, status, JSON.stringify(res.body));
  return res.body;
};

test('db: what goes in is copied, nested values included', () => {
  const t = createDb().books;
  const row = { title: 'a', tags: ['x'], dimensions: { w: 1 } };
  const { id } = t.insert(row);
  row.title = 'z';
  row.tags.push('y');
  row.dimensions.w = 9;
  assert.deepEqual(t.find(id), { id, title: 'a', tags: ['x'], dimensions: { w: 1 } });
});

test('db: what comes out of insert is a copy', () => {
  const t = createDb().books;
  const out = t.insert({ title: 'a', tags: ['x'] });
  out.tags.push('y');
  out.title = 'z';
  assert.deepEqual(t.find(out.id), { id: out.id, title: 'a', tags: ['x'] });
});

test('db: find, all and where return deep copies', () => {
  const t = createDb().books;
  const { id } = t.insert({ title: 'a', tags: ['x'], dimensions: { w: 1 } });
  t.find(id).tags.push('1');
  t.all()[0].dimensions.w = 2;
  t.where(() => true)[0].title = 'changed';
  assert.deepEqual(t.find(id), { id, title: 'a', tags: ['x'], dimensions: { w: 1 } });
});

test('db: update copies the patch in and a copy out, and keeps the id', () => {
  const t = createDb().books;
  const { id } = t.insert({ title: 'a', tags: ['x'] });
  const patch = { tags: ['p'], id: 999 };
  const out = t.update(id, patch);
  patch.tags.push('q');
  out.tags.push('r');
  assert.deepEqual(t.find(id), { id, title: 'a', tags: ['p'] });
  assert.equal(t.find(999), null);
  assert.equal(t.update(12345, { title: 'x' }), null);
});

test('db: ids, ordering and removal behave as before', () => {
  const t = createDb().books;
  assert.equal(t.insert({ n: 1 }).id, 1);
  assert.equal(t.insert({ id: 10, n: 2 }).id, 10);
  assert.equal(t.insert({ n: 3 }).id, 11);
  assert.deepEqual(t.all().map((r) => r.n), [1, 2, 3]);
  assert.equal(t.remove(10), true);
  assert.equal(t.remove(10), false);
  assert.deepEqual(t.where((r) => r.n > 1).map((r) => r.n), [3]);
});

test('db: stays fast with thousands of rows', () => {
  const t = createDb().books;
  for (let i = 0; i < 5000; i++) t.insert({ n: i, tags: ['a', 'b'] });
  const start = Date.now();
  for (let i = 1; i <= 5000; i++) assert.equal(t.find(i).n, i - 1);
  assert.ok(Date.now() - start < 5000, 'find() is far too slow');
});

test('books: a patch persists, including nested values, and keeps the id', () => {
  const app = createSeededApp();
  ok(app.handle('PATCH', '/books/3', { body: { tags: ['new'], price: 20, id: 77 } }));
  const book = ok(app.handle('GET', '/books/3'));
  assert.equal(book.id, 3);
  assert.equal(book.price, 20);
  assert.deepEqual(book.tags, ['new']);
  assert.equal(app.handle('GET', '/books/77').status, 404);
});

test('books: the patch body is not kept by the store', () => {
  const app = createSeededApp();
  const body = { tags: ['one'] };
  ok(app.handle('PATCH', '/books/4', { body }));
  body.tags.push('two');
  assert.deepEqual(ok(app.handle('GET', '/books/4')).tags, ['one']);
});

test('books: an invalid patch changes nothing at all', () => {
  const app = createSeededApp();
  const before = JSON.stringify(ok(app.handle('GET', '/books/5')));
  assert.equal(app.handle('PATCH', '/books/5', { body: { tags: ['ok'], authorId: 99 } }).status, 422);
  assert.equal(app.handle('PATCH', '/books/5', { body: { tags: 'nope' } }).status, 422);
  assert.equal(JSON.stringify(ok(app.handle('GET', '/books/5'))), before);
});

test('books: listing results are copies too', () => {
  const app = createSeededApp();
  const page = ok(app.handle('GET', '/books'));
  page.items[0].tags.push('x');
  page.items[0].price = 0;
  const again = ok(app.handle('GET', '/books'));
  assert.deepEqual(again.items[0].tags, ['travel', 'history']);
  assert.equal(again.items[0].price, 12.5);
});

test('orders: lines keep the price and title from the time of purchase', () => {
  const app = createSeededApp();
  const created = ok(app.handle('POST', '/orders', { body: { customerId: 'c', lines: [{ bookId: 4, qty: 2 }] } }), 201);
  assert.equal(created.total, 22.5);
  ok(app.handle('PATCH', '/books/4', { body: { price: 99, title: 'Renamed' } }));
  const again = ok(app.handle('GET', `/orders/${created.id}`));
  assert.equal(again.total, 22.5);
  assert.deepEqual(again.lines.map((l) => [l.title, l.price]), [['Night Ferry', 11.25]]);
});

test('orders: a response can be changed without touching the stored order', () => {
  const app = createSeededApp();
  const created = ok(app.handle('POST', '/orders', { body: { customerId: 'c', lines: [{ bookId: 1, qty: 1 }] } }), 201);
  created.lines[0].price = 0;
  created.total = 0;
  assert.equal(ok(app.handle('GET', `/orders/${created.id}`)).total, 12.5);
});

test('seeded apps are independent of each other', () => {
  const a = createSeededApp();
  const b = createSeededApp();
  ok(a.handle('PATCH', '/books/1', { body: { price: 1, tags: ['only-a'] } }));
  assert.equal(ok(b.handle('GET', '/books/1')).price, 12.5);
  assert.deepEqual(ok(b.handle('GET', '/books/1')).tags, ['travel', 'history']);
});
