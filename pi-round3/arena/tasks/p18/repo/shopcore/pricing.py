"""The pricing functions."""
from .catalog import CATALOG


def price_for(sku, qty):
    """Price of `qty` units of `sku`, in euro cents."""
    return CATALOG[sku]["eur_cents"] * qty


def price_bulk(sku, qty):
    """Price of `qty` units of `sku` with the quantity discount, in euro cents."""
    item = CATALOG[sku]
    unit = item["eur_cents"]
    for min_qty, tier_price in sorted(item["bulk"]):
        if qty >= min_qty:
            unit = tier_price
    return unit * qty
