# discounts

`discounts.apply_discounts(cart, rules)` prices a shopping cart. All money is in **integer cents**.

```python
from discounts import apply_discounts

cart = [
    {"sku": "A", "unit_cents": 1000, "qty": 3, "category": "book"},
    {"sku": "B", "unit_cents": 250, "qty": 2},                       # "category" is optional
]
rules = [
    {"type": "bogo", "sku": "A"},
    {"type": "percent", "value": 10, "category": "book"},
    {"type": "fixed", "value": 500, "min_subtotal": 3000},
    {"type": "cap", "max_percent": 30},
]
apply_discounts(cart, rules)
# {'subtotal': 3500, 'discount': 1050, 'total': 2450, 'applied': [(0, 1000), (1, 200), (2, 500)]}
```

## Result

A dict with

* `subtotal`: sum of `unit_cents * qty` over all lines, before any discount,
* `discount`: the total discount (after the cap),
* `total`: `subtotal - discount`,
* `applied`: a list of `(rule_index, cents)` for every discount rule (bogo, percent, fixed) that gave a discount greater than
  zero, in rule order. It shows what each rule gave *before* the cap is applied; cap rules never appear in it.

An empty cart gives zeros and an empty `applied` list.

## Rules, applied in this order

1. **bogo** `{"type": "bogo", "sku": S}`: on every cart line with SKU `S` every second item is free, i.e. `qty // 2` items
   (three items: one free; five: two free). bogo rules are applied before all others.
2. **percent** `{"type": "percent", "value": P, "category": C}`: takes `P` percent off the *remaining* amount of every line
   that matches. `category` is optional: without it the rule matches every line; with it only lines whose `category` equals `C`.
   The discount of a line is rounded half up to a whole cent: `(amount * P + 50) // 100`. Percent rules are applied one after
   the other in rule order, each one on what is left after the previous ones (10 % and then 10 % make 19 %, not 20 %).
3. **fixed** `{"type": "fixed", "value": V, "min_subtotal": M}`: takes `V` cents off the cart. `min_subtotal` is optional
   (default 0); the rule only applies if the *original* subtotal (before any discount) is at least `M`; exactly `M` is enough.
   This discount never takes the cart below zero.
4. **cap** `{"type": "cap", "max_percent": P}`: the total discount may not be more than `P` percent of the original subtotal,
   rounded down to a whole cent. With several cap rules the smallest limit counts.

## Errors

`ValueError` for: a negative `qty` or `unit_cents`; a rule with an unknown `type`; a percent `value` outside 0..100; a negative
fixed `value`; a cap `max_percent` outside 0..100. Rules are validated even if the cart is empty.
