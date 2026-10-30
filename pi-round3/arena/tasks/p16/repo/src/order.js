'use strict';
const { discount } = require('./discount');
const { shippingFee } = require('./shipping');
const { taxFor } = require('./tax');

function subtotal(lines) {
  return lines.reduce((sum, line) => sum + line.unitCents * line.qty, 0);
}

function orderTotal(order) {
  const sub = subtotal(order.lines);
  const disc = discount(sub, order.coupon);
  const shipping = shippingFee(sub);
  const tax = taxFor(sub - disc, order.country);
  return { subtotal: sub, discount: disc, shipping, tax, total: sub - disc + shipping + tax };
}

module.exports = { subtotal, orderTotal };
