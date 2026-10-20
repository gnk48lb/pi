'use strict';

/** Round to at most 4 decimals and drop trailing zeros: 2.50004 -> "2.5", 4 -> "4". */
function fmtNum(n) {
  return String(Number(n.toFixed(4)));
}

/**
 * One line per column: `name: count=3 min=1.5 max=4 mean=2.6667 sum=8`.
 * @param {{name: string, count: number, min: number, max: number, mean: number, sum: number}[]} stats
 * @returns {string} newline-terminated text
 */
function formatText(stats) {
  if (stats.length === 0) return 'No numeric columns found\n';
  const lines = stats.map(
    (s) =>
      `${s.name}: count=${s.count} min=${fmtNum(s.min)} max=${fmtNum(s.max)} ` +
      `mean=${fmtNum(s.mean)} sum=${fmtNum(s.sum)}`
  );
  return lines.join('\n') + '\n';
}

module.exports = { fmtNum, formatText };
