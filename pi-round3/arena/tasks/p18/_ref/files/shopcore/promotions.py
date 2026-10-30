from .currency import format_money
from .pricing import price_bulk, price_for

# pricing strategies by name; every strategy has the signature of the pricing functions
PRICERS = {"standard": price_for, "bulk": price_bulk}


def quote(kind, sku, qty, currency):
    """A human readable quote, e.g. 'A-1 x 2 = USD 27.50'."""
    cents = PRICERS[kind](sku, qty, currency=currency)
    return "%s x %d = %s" % (sku, qty, format_money(cents, currency))


def cart_quote(cart, kind="standard"):
    """What the cart costs with the named pricing strategy."""
    pricer = PRICERS[kind]
    return sum(pricer(sku, qty, currency=cart.currency) for sku, qty in cart.lines)
