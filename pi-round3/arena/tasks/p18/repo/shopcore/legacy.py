"""Kept for the old nightly billing batch."""
from . import pricing as _pricing

_pf = _pricing.price_for


def legacy_total(cart):
    """Total of a cart as the old batch computes it."""
    total = 0
    for sku, qty in cart.lines:
        total += _pf(sku, qty)
    return total
