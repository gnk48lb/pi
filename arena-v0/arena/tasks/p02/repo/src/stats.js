'use strict';

/** null for an empty cell, NaN for a non-numeric cell, otherwise the number. */
function toNumber(cell) {
  const s = String(cell === undefined ? '' : cell).trim();
  if (s === '') return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : NaN;
}

/**
 * Numeric columns of a parsed table, in file order. Empty cells are skipped.
 * @param {{header: string[], rows: string[][]}} table
 * @param {string[] | null} only  restrict to these column names
 * @returns {{name: string, values: number[]}[]}
 */
function numericColumns(table, only) {
  const out = [];
  table.header.forEach((name, idx) => {
    if (only && !only.includes(name)) return;
    const values = [];
    let numeric = true;
    for (const row of table.rows) {
      const n = toNumber(row[idx]);
      if (n === null) continue;
      if (Number.isNaN(n)) {
        numeric = false;
        break;
      }
      values.push(n);
    }
    if (numeric && values.length > 0) out.push({ name, values });
  });
  return out;
}

/** @param {number[]} values  non-empty */
function summarize(values) {
  let min = Infinity;
  let max = -Infinity;
  let sum = 0;
  for (const v of values) {
    if (v < min) min = v;
    if (v > max) max = v;
    sum += v;
  }
  return { count: values.length, min, max, mean: sum / values.length, sum };
}

module.exports = { numericColumns, summarize };
