from functools import partial

from .currency import format_money
from .orders import order_total
from .pricing import price_for


def list_prices(skus, currency):
    """The price of one unit of each sku, formatted: ['USD 13.75', ...]."""
    one = partial(price_for, qty=1, currency=currency)
    return [format_money(one(sku), currency) for sku in skus]


def revenue_by_currency(orders):
    """{'USD': cents, ...}: what the orders add up to in each currency."""
    totals = {}
    for order in orders:
        totals[order.currency] = totals.get(order.currency, 0) + order_total(order)
    return totals
