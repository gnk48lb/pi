'use strict';
const { dayNumber } = require('./dates');

// Amount in cents to charge right now when a subscription moves from a plan costing `oldCents` to one costing
// `newCents` on `changeIso`, inside the cycle `bounds` ({ start, next, days }).
function prorate(oldCents, newCents, changeIso, bounds) {
  const diff = newCents - oldCents;
  if (diff <= 0) return 0;
  const remaining = dayNumber(bounds.next) - dayNumber(changeIso);
  const cycleDays = dayNumber(bounds.next) - dayNumber(bounds.start);
  // diff * remaining / cycleDays, rounded half up, in integers (no floating point)
  return Math.floor((2 * diff * remaining + cycleDays) / (2 * cycleDays));
}

module.exports = { prorate };
