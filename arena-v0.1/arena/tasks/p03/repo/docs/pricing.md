# Pricing

Every order total in invtrack is produced by `invtrack.pricing.calc_total(items, tax=0.0)`.

* `items` is a list of item dicts (`price`, `qty`, ...).
* `tax` is the tax rate as a fraction.  `calc_total(items, tax=0.2)` adds 20 %.
* The total is rounded to two decimals (`round(x, 2)`).

The reports (`invtrack.reports`) and the CSV export (`invtrack.export`) call `calc_total`
for every order, so a change in the pricing rules only has to be made in one place.
