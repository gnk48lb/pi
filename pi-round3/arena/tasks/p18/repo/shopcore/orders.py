from .pricing import price_for as unit_price


class Order:
    """A placed order: lines are (sku, qty) pairs."""

    def __init__(self, number, currency, lines):
        self.number = number
        self.currency = currency
        self.lines = list(lines)


def order_total(order):
    return sum(unit_price(sku, qty) for sku, qty in order.lines)
