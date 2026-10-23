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

/** Pretty-printed JSON: {"columns": {"<name>": {count, min, max, mean, sum}}}. */
function formatJson(stats) {
  const columns = {};
  for (const s of stats) {
    columns[s.name] = {
      count: s.count,
      min: Number(fmtNum(s.min)),
      max: Number(fmtNum(s.max)),
      mean: Number(fmtNum(s.mean)),
      sum: Number(fmtNum(s.sum)),
    };
  }
  return JSON.stringify({ columns }, null, 2) + '\n';
}

/** Plain-text table: left-aligned cells padded to the widest cell of their column. */
function formatTable(stats) {
  const header = ['column', 'count', 'min', 'max', 'mean', 'sum'];
  const rows = stats.map((s) => [
    s.name,
    String(s.count),
    fmtNum(s.min),
    fmtNum(s.max),
    fmtNum(s.mean),
    fmtNum(s.sum),
  ]);
  const widths = header.map((h, i) => Math.max(h.length, ...rows.map((r) => r[i].length)));
  const line = (cells) => cells.map((c, i) => c.padEnd(widths[i])).join(' | ').trimEnd();
  const separator = widths.map((w) => '-'.repeat(w)).join('-|-');
  return [line(header), separator, ...rows.map(line)].join('\n') + '\n';
}

const FORMATTERS = { text: formatText, json: formatJson, table: formatTable };

module.exports = { fmtNum, formatText, formatJson, formatTable, FORMATTERS };
