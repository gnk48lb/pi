"""The pricing functions."""
from .catalog import CATALOG
from .currency import convert


def price_for(sku, qty, *, currency):
    """Price of `qty` units of `sku`, in cents of `currency`."""
    return convert(CATALOG[sku]["eur_cents"] * qty, currency)


def price_bulk(sku, qty, *, currency):
    """Price of `qty` units of `sku` with the quantity discount, in cents of `currency`."""
    item = CATALOG[sku]
    unit = item["eur_cents"]
    for min_qty, tier_price in sorted(item["bulk"]):
        if qty >= min_qty:
            unit = tier_price
    return convert(unit * qty, currency)
