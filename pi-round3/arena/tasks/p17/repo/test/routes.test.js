'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { buildApp } = require('../src/app');

test('the public routes are served under /api/v2', () => {
  const app = buildApp();
  assert.ok(app.has('GET', '/api/v2/customers'));
  assert.ok(app.has('GET', '/api/v2/customers/:id'));
  assert.ok(app.has('POST', '/api/v2/orders/:id/cancel'));
  assert.ok(app.has('GET', '/api/v2/invoices/:id/pdf'));
  assert.ok(app.has('GET', '/api/v2/version'));
  assert.ok(!app.has('GET', '/api/v1/customers'));
});

test('the routes marked "legacy: keep" stay under /api/v1', () => {
  const app = buildApp();
  assert.ok(app.has('GET', '/api/v1/customers/:id/export'));
  assert.ok(app.has('GET', '/api/v1/products/:sku/stock'));
  assert.ok(app.has('GET', '/api/v1/health'));
});

test('the route table has not lost or gained routes', () => {
  assert.strictEqual(buildApp().routes.length, 24);
});
