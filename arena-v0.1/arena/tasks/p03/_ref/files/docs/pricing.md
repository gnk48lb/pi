# Pricing

Every order total in invtrack is produced by `invtrack.pricing.compute_order_total(items, tax_rate=0.0)`.

* `items` is a list of item dicts (`price`, `qty`, ...).
* `tax_rate` is the tax rate as a fraction.  `compute_order_total(items, tax_rate=0.2)` adds 20 %.
* The total is rounded to two decimals (`round(x, 2)`).

The reports (`invtrack.reports`) and the CSV export (`invtrack.export`) call `compute_order_total`
for every order, so a change in the pricing rules only has to be made in one place.

`calc_total(items, tax=0.0)` is a deprecated alias of `compute_order_total` and will be removed in a future release.
It emits a `DeprecationWarning`.
