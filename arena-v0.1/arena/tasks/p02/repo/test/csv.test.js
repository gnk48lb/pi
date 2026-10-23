'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { parseCsv } = require('../src/csv');

test('parses a header and rows', () => {
  assert.deepEqual(parseCsv('a,b\n1,2\n3,4\n'), { header: ['a', 'b'], rows: [['1', '2'], ['3', '4']] });
});

test('handles quoted fields, escaped quotes and commas inside quotes', () => {
  const t = parseCsv('a,b\n"x, y","say ""hi"""\n');
  assert.deepEqual(t.rows, [['x, y', 'say "hi"']]);
});

test('accepts CRLF line ends and ignores blank lines', () => {
  const t = parseCsv('a,b\r\n1,2\r\n\r\n3,4');
  assert.deepEqual(t.rows, [['1', '2'], ['3', '4']]);
});

test('empty input gives an empty header', () => {
  assert.deepEqual(parseCsv(''), { header: [], rows: [] });
});
