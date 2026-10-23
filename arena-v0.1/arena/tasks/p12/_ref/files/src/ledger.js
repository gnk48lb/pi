'use strict';
const { SpendError } = require('./errors');

// A comma is accepted as thousands separator, between groups of exactly three digits: "1,200.50"
const THOUSANDS = /^[+-]?\d{1,3}(,\d{3})+(\.\d*)?$/;

// "12.50" -> 1250 (whole cents)
function parseAmount(text) {
  const plain = text !== undefined && THOUSANDS.test(text.trim()) ? text.trim().replace(/,/g, '') : text;
  const value = Number(plain);
  if (text === undefined || text.trim() === '' || !Number.isFinite(value)) {
    throw new SpendError(`bad amount ${JSON.stringify(text)}`);
  }
  return Math.round(value * 100);
}

// cents in `currency` -> cents in US dollars; `rates` maps a currency code to the value of one unit in dollars
function toDollars(cents, currency, rates) {
  const rate = rates[currency];
  if (rate === undefined) {
    throw new SpendError(`unknown currency ${JSON.stringify(currency)}`);
  }
  return Math.round(cents * rate);
}

function inMonth(row, month) {
  return row.date.startsWith(month);
}

// Dollar cents per category.  Rows outside `month` (YYYY-MM, optional) are skipped.
function summarize(rows, rates, month) {
  const totals = {};
  for (const row of rows) {
    if (month && !inMonth(row, month)) continue;
    let cents;
    try {
      cents = toDollars(parseAmount(row.amount), row.currency, rates);
    } catch (err) {
      if (err instanceof SpendError) throw new SpendError(`line ${row._row}: ${err.message}`);
      throw err;
    }
    totals[row.category] = (totals[row.category] || 0) + cents;
  }
  return totals;
}

module.exports = { parseAmount, toDollars, summarize };
