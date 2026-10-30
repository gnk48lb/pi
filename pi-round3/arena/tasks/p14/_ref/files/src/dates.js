'use strict';
// Dates are ISO strings "YYYY-MM-DD": no Date objects, no time zones, so nothing depends on where the code runs.

function isLeapYear(y) {
  return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
}

function daysInMonth(y, m) {
  const lengths = [31, isLeapYear(y) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return lengths[m - 1];
}

function parse(iso) {
  const found = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!found) throw new Error(`invalid date: ${iso}`);
  const y = Number(found[1]);
  const m = Number(found[2]);
  const d = Number(found[3]);
  if (m < 1 || m > 12 || d < 1 || d > daysInMonth(y, m)) throw new Error(`invalid date: ${iso}`);
  return { y, m, d };
}

function format({ y, m, d }) {
  return `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

// Days since 1970-01-01 in the proleptic Gregorian calendar (the usual "days from civil" algorithm).
function dayNumber(iso) {
  let { y, m, d } = parse(iso);
  if (m <= 2) y -= 1;
  const era = Math.floor(y / 400);
  const yoe = y - era * 400;
  const doy = Math.floor((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5) + d - 1;
  const doe = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
  return era * 146097 + doe - 719468;
}

// Month arithmetic on { y, m } (m is 1-12); n may be negative.
function addMonths({ y, m }, n) {
  const index = y * 12 + (m - 1) + n;
  return { y: Math.floor(index / 12), m: (index % 12) + 1 };
}

module.exports = { isLeapYear, daysInMonth, parse, format, dayNumber, addMonths };
