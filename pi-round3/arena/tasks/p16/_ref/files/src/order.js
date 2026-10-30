'use strict';
const { discount } = require('./discount');
const { shippingFee } = require('./shipping');
const { taxFor } = require('./tax');

function subtotal(lines) {
  let sum = 0;
  for (const line of lines) {
    if (!Number.isInteger(line.qty) || line.qty < 0) throw new RangeError(`bad quantity: ${line.qty}`);
    sum += line.unitCents * line.qty;
  }
  return sum;
}

function orderTotal(order) {
  const sub = subtotal(order.lines);
  if (sub === 0) return { subtotal: 0, discount: 0, shipping: 0, tax: 0, total: 0 };
  const disc = discount(sub, order.coupon);
  const net = sub - disc;
  const digitalOnly = order.lines.filter((line) => line.qty > 0).every((line) => line.digital === true);
  const shipping = shippingFee(net, { digitalOnly });
  const tax = taxFor(net + shipping, order.country);
  return { subtotal: sub, discount: disc, shipping, tax, total: net + shipping + tax };
}

module.exports = { subtotal, orderTotal };
