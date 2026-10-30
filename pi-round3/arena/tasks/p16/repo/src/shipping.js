'use strict';

const FREE_FROM = 5000;
const FLAT_FEE = 499;

// Shipping in cents for an order whose net amount (subtotal minus discount) is `net`.
function shippingFee(net) {
  return net > FREE_FROM ? 0 : FLAT_FEE;
}

module.exports = { shippingFee, FREE_FROM, FLAT_FEE };
