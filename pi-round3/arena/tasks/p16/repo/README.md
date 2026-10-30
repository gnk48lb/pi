# checkout

Order totals for a small web shop.

* All amounts are **integer cents**. Rounding is **half up** (2.5 cents become 3, 2.4999 cents become 2).
* An order is `{ lines: [{ unitCents, qty, digital? }], coupon?, country }`.

```js
const { subtotal, discount, shippingFee, taxFor, orderTotal } = require('./src');
```

## Total

`orderTotal(order)` returns `{ subtotal, discount, shipping, tax, total }`, computed in this order:

1. `subtotal` is the sum of `unitCents * qty` over the lines. `qty` must be a non-negative integer, otherwise a
   `RangeError` is thrown. A line with `qty` 0 counts for nothing and is ignored by the rules below.
2. `discount` is `discount(subtotal, order.coupon)`.
3. The *net amount* is `subtotal - discount`.
4. `shipping` is `shippingFee(net, { digitalOnly })`, where `digitalOnly` is true when every line with a quantity above 0
   has `digital: true`.
5. `tax` is `taxFor(net + shipping, order.country)`: tax is charged on the net amount **and** on the shipping.
6. `total` is `net + shipping + tax`.

An order whose subtotal is 0 (no lines, or only lines with quantity 0) costs nothing: all five amounts are 0, and the
country is not even looked at.

## Coupons

`discount(subtotal, coupon)` is the discount in cents; no coupon means 0.

* `{ type: 'percent', value }`: `value` is an integer from 0 to 100 (anything else throws a `RangeError`); the discount is
  `subtotal * value / 100`, rounded half up.
* `{ type: 'fixed', value }`: the discount is `value` cents.
* Any other `type` throws `Error('unknown coupon type: <type>')`.
* A coupon may have a `minSubtotal`: it only applies when `subtotal >= minSubtotal` (the subtotal before any discount);
  otherwise the discount is 0. The type and the value are validated first, whether or not the minimum is reached.
* The discount never exceeds the subtotal.

## Shipping

`shippingFee(net, { digitalOnly })` is 0 for a digital-only order. Otherwise it is 0 when `net` is **5000 cents or more**
(an order of exactly 50.00 ships free) and the flat fee of 499 cents below that.

## Tax

`taxFor(base, country)`: the tax rate in percent is DE 19, FR 20, GB 20, NL 21, US 0. The tax is `base * rate / 100`,
rounded half up. Any other country throws `Error('unknown country: <code>')`.

## Tests

`npm test` runs the tests in `test/`.
