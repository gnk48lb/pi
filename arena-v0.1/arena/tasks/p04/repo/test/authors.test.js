'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { fresh, ok } = require('./helpers');

test('lists the four seeded authors', () => {
  const app = fresh();
  assert.equal(ok(app.handle('GET', '/authors')).length, 4);
});

test('creating an author returns 201 and the new id', () => {
  const app = fresh();
  const created = ok(app.handle('POST', '/authors', { body: { name: 'Mina Okafor', born: 1990 } }), 201);
  assert.equal(created.id, 5);
  assert.equal(ok(app.handle('GET', '/authors/5')).name, 'Mina Okafor');
});

test('an author needs a name', () => {
  const app = fresh();
  assert.equal(app.handle('POST', '/authors', { body: { born: 1990 } }).status, 422);
});

test('changing a returned author does not change the stored author', () => {
  const app = fresh();
  const list = ok(app.handle('GET', '/authors'));
  list[0].name = 'Somebody Else';
  assert.equal(ok(app.handle('GET', '/authors/1')).name, 'Ursula Vance');
});
