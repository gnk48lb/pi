'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { parseCsv } = require('../src/csv');
const { parseAmount } = require('../src/ledger');

test('a byte order mark and CRLF line endings are not part of the data', () => {
  const rows = parseCsv('﻿date,currency\r\n2026-03-01,EUR\r\n');
  assert.deepEqual(Object.keys(rows[0]), ['_row', 'date', 'currency']);
  assert.equal(rows[0].currency, 'EUR');
});

test('quoted fields may contain commas, quotes and line breaks', () => {
  const rows = parseCsv('a,b\r\n"x, y","say ""hi"""\r\n"line 1\nline 2",z\r\n');
  assert.equal(rows[0].a, 'x, y');
  assert.equal(rows[0].b, 'say "hi"');
  assert.equal(rows[1].a, 'line 1\nline 2');
  assert.equal(rows[1].b, 'z');
});

test('thousands separators are accepted only between groups of three digits', () => {
  assert.equal(parseAmount('1,200.50'), 120050);
  assert.equal(parseAmount('12,345,678'), 1234567800);
  assert.throws(() => parseAmount('12,5'), /bad amount/);
  assert.throws(() => parseAmount('1,23'), /bad amount/);
});

test('the March export from the new accounting system has five columns in every row', () => {
  const rows = parseCsv(fs.readFileSync(path.join(__dirname, '..', 'data', 'march.csv'), 'utf8'));
  assert.equal(rows.length, 9);
  for (const row of rows) assert.equal(Object.keys(row).length, 6);
});
