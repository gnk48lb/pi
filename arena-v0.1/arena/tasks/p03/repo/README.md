# invtrack

Tiny order bookkeeping toolkit: load orders from JSON, price them, report and export.

## Pricing

All prices go through one function:

```python
from invtrack.pricing import calc_total

calc_total([{"sku": "A1", "price": 10.0, "qty": 2}], tax=0.2)   # -> 24.0
```

`tax` is a fraction (`0.2` means 20 %). The result is rounded to two decimals.

## Command line

```
python3 -m invtrack.cli total data/sample.json --tax 0.2     # grand total of all orders
python3 -m invtrack.cli report data/sample.json              # one line per order, biggest first
python3 -m invtrack.cli csv data/sample.json --tax 0.2       # CSV: id, items, total
```

## Tests

```
python3 -m unittest
```
