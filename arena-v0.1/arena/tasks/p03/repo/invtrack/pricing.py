"""Order pricing."""


def line_total(item):
    """Price of one order line (no tax)."""
    return item["price"] * item["qty"]


def calc_total(items, tax=0.0):
    """Return the total of `items` including tax.

    `tax` is a fraction (0.2 means 20 %).  The result is rounded to two decimals.
    """
    subtotal = sum(line_total(i) for i in items)
    return round(subtotal * (1 + tax), 2)
