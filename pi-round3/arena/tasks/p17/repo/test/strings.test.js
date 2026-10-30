'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { load } = require('../src/i18n');

test('the greeting says "\u00e0 bord"', () => {
  assert.strictEqual(load().greeting, 'Bienvenue \u00e0 bord');
});

test('the other messages are intact', () => {
  const m = load();
  assert.strictEqual(m.farewell, '\u00c0 bient\u00f4t');
  assert.strictEqual(m['cart.title'], 'R\u00e9capitulatif de la commande');
  assert.strictEqual(m.footer, '\u00a9 2019 \u00c9quipe Plateforme');
});
