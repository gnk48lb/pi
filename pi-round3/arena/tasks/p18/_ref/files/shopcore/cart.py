from .pricing import price_for


class Cart:
    """A shopping cart in one currency."""

    def __init__(self, currency="EUR"):
        self.currency = currency
        self.lines = []

    def add(self, sku, qty=1):
        self.lines.append((sku, qty))

    def total(self):
        return sum(price_for(sku, qty, currency=self.currency) for sku, qty in self.lines)
