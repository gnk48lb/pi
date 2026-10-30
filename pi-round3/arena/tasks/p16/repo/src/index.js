'use strict';
const { discount } = require('./discount');
const { shippingFee } = require('./shipping');
const { taxFor } = require('./tax');
const { subtotal, orderTotal } = require('./order');

module.exports = { subtotal, discount, shippingFee, taxFor, orderTotal };
