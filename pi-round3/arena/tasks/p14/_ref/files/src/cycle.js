'use strict';
const { daysInMonth, parse, format, dayNumber, addMonths } = require('./dates');

// Start of the cycle that begins in month (y, m) for a subscription anchored on `anchorDay`.
function startIn(anchorDay, y, m) {
  return format({ y, m, d: Math.min(anchorDay, daysInMonth(y, m)) });
}

// The starts of the first `count` cycles, beginning with the cycle that starts on `firstStart`.
function cycleStarts(anchorDay, firstStart, count) {
  const first = parse(firstStart);
  const out = [];
  for (let i = 0; i < count; i++) {
    const month = addMonths(first, i);
    out.push(startIn(anchorDay, month.y, month.m));
  }
  return out;
}

// The cycle that contains `iso`: { start, next, days } with start <= iso < next.
function cycleBounds(anchorDay, iso) {
  const { y, m } = parse(iso);
  let start = startIn(anchorDay, y, m);
  let month = { y, m };
  if (start > iso) {
    month = addMonths(month, -1);
    start = startIn(anchorDay, month.y, month.m);
  }
  const following = addMonths(month, 1);
  const next = startIn(anchorDay, following.y, following.m);
  return { start, next, days: dayNumber(next) - dayNumber(start) };
}

module.exports = { cycleStarts, cycleBounds };
