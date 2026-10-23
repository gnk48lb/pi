'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { parseAmount, toDollars, summarize } = require('../src/ledger');
const { SpendError } = require('../src/errors');

const RATES = { USD: 1, EUR: 1.25 };

test('amounts become whole cents', () => {
  assert.equal(parseAmount('12.50'), 1250);
  assert.equal(parseAmount('8.2'), 820);
  assert.equal(parseAmount('1200'), 120000);
});

test('bad amounts are input errors', () => {
  assert.throws(() => parseAmount('abc'), SpendError);
  assert.throws(() => parseAmount(''), SpendError);
});

test('currencies are converted with the rate and rounded to cents', () => {
  assert.equal(toDollars(1000, 'EUR', RATES), 1250);
  assert.equal(toDollars(1000, 'USD', RATES), 1000);
  assert.throws(() => toDollars(1000, 'XYZ', RATES), /unknown currency "XYZ"/);
});

test('summarize adds the rows up per category', () => {
  const rows = [
    { _row: 2, date: '2026-01-05', category: 'Food', amount: '10.00', currency: 'USD' },
    { _row: 3, date: '2026-01-06', category: 'Food', amount: '8.00', currency: 'EUR' },
    { _row: 4, date: '2026-02-01', category: 'Travel', amount: '5.00', currency: 'USD' },
  ];
  assert.deepEqual(summarize(rows, RATES), { Food: 2000, Travel: 500 });
  assert.deepEqual(summarize(rows, RATES, '2026-01'), { Food: 2000 });
});

test('errors name the row', () => {
  const rows = [{ _row: 7, date: '2026-01-05', category: 'Food', amount: '10.00', currency: 'XYZ' }];
  assert.throws(() => summarize(rows, RATES), /line 7: unknown currency "XYZ"/);
});
