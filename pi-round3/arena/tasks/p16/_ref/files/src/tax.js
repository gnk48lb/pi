'use strict';
const { roundDiv } = require('./money');

const RATES = { DE: 19, FR: 20, GB: 20, NL: 21, US: 0 };

// Tax in cents on `base` cents for a customer in `country`.
function taxFor(base, country) {
  const rate = RATES[country];
  if (rate === undefined) throw new Error(`unknown country: ${country}`);
  return roundDiv(base * rate, 100);
}

module.exports = { taxFor, RATES };
