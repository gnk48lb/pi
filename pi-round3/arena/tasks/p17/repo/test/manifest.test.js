'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const manifest = require('../config/manifest.json');

test('the service version is 2.0.0', () => {
  assert.strictEqual(manifest.version, '2.0.0');
});

test('the schema version and the dependencies are untouched', () => {
  assert.strictEqual(manifest.schemaVersion, 3);
  assert.strictEqual(manifest.deps['express-lite'].version, '^4.1.0');
  assert.strictEqual(manifest.deps['pg-shim'].version, '2.3.1');
});
