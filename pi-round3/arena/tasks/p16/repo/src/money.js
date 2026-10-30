'use strict';

// n / d rounded half up, for integers n >= 0 and d > 0 (no floating point involved).
function roundDiv(n, d) {
  return Math.floor((2 * n + d) / (2 * d));
}

module.exports = { roundDiv };
