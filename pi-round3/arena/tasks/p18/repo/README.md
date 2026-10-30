# shopcore

Pricing helpers of a small shop. The catalog (`shopcore/catalog.py`) holds the prices in **euro cents**;
`shopcore/currency.py` converts an amount of euro cents into another currency (`convert`, rounding half up) and formats it.

## Pricing

`shopcore/pricing.py` has the two pricing functions. Both take a catalog sku and a quantity and return the price of that
many units:

* `price_for(sku, qty)`: unit price times quantity;
* `price_bulk(sku, qty)`: like `price_for`, but with the quantity discount of the catalog (the unit price of the best tier
  whose minimum quantity is reached).

They are used all over the package: directly, under other names, through the registry of `shopcore/promotions.py`, and in
the batch jobs.

## Status

The shop started to sell in USD, GBP and CHF, but the prices are still computed in euros: a USD cart shows the euro
amount with a "USD" label. Prices must be computed **in the currency of the cart / order / request they belong to**.

## Tests

`python3 -m unittest` runs the tests in `tests/`. They do not exercise every entry point of the package.
