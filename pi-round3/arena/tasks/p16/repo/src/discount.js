'use strict';

// The discount in cents that `coupon` gives on an order with the given subtotal.
function discount(subtotal, coupon) {
  if (!coupon) return 0;
  switch (coupon.type) {
    case 'percent':
      if (!Number.isInteger(coupon.value) || coupon.value < 0 || coupon.value > 100) {
        throw new RangeError(`bad percentage: ${coupon.value}`);
      }
      return Math.floor((subtotal * coupon.value) / 100);
    case 'fixed':
      return coupon.value;
    default:
      throw new Error(`unknown coupon type: ${coupon.type}`);
  }
}

module.exports = { discount };
