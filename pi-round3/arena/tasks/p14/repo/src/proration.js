'use strict';
const { dayNumber } = require('./dates');

// Amount in cents to charge right now when a subscription moves from a plan costing `oldCents` to one costing
// `newCents` on `changeIso`, inside the cycle `bounds` ({ start, next, days }).
function prorate(oldCents, newCents, changeIso, bounds) {
  const diff = newCents - oldCents;
  if (diff <= 0) return diff;
  const remaining = dayNumber(bounds.next) - dayNumber(changeIso) - 1;
  const cycleDays = 30;
  return Math.floor((diff * remaining) / cycleDays);
}

module.exports = { prorate };
