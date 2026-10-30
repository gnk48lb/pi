'use strict';
const { roundDiv } = require('./money');

// The discount in cents that `coupon` gives on an order with the given subtotal.
function discount(subtotal, coupon) {
  if (!coupon) return 0;
  let amount;
  switch (coupon.type) {
    case 'percent':
      if (!Number.isInteger(coupon.value) || coupon.value < 0 || coupon.value > 100) {
        throw new RangeError(`bad percentage: ${coupon.value}`);
      }
      amount = roundDiv(subtotal * coupon.value, 100);
      break;
    case 'fixed':
      amount = coupon.value;
      break;
    default:
      throw new Error(`unknown coupon type: ${coupon.type}`);
  }
  if (coupon.minSubtotal !== undefined && subtotal < coupon.minSubtotal) return 0;
  return Math.min(amount, subtotal);
}

module.exports = { discount };
