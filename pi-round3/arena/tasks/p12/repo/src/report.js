'use strict';
const { formatAmount } = require('./format');

// One line per category (sorted by name) and a TOTAL line.
function renderReport(totals) {
  const names = Object.keys(totals).sort();
  const total = names.reduce((sum, name) => sum + totals[name], 0);
  const width = Math.max(5, ...names.map((name) => name.length));
  const lines = names.map((name) => `${name.padEnd(width)}  ${formatAmount(totals[name]).padStart(12)}`);
  lines.push(`${'TOTAL'.padEnd(width)}  ${formatAmount(total).padStart(12)}`);
  return lines.join('\n') + '\n';
}

module.exports = { renderReport };
