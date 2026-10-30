"""Order pricing."""
import warnings


def line_total(item):
    """Price of one order line (no tax)."""
    return item["price"] * item["qty"]


def compute_order_total(items, tax_rate=0.0):
    """Return the total of `items` including tax.

    `tax_rate` is a fraction (0.2 means 20 %).  The result is rounded to two decimals.
    """
    subtotal = sum(line_total(i) for i in items)
    return round(subtotal * (1 + tax_rate), 2)


def calc_total(items, tax=0.0):
    """Deprecated alias of `compute_order_total` (the parameter `tax` is now `tax_rate`)."""
    warnings.warn("calc_total() is deprecated, use compute_order_total(items, tax_rate=...)",
                  DeprecationWarning, stacklevel=2)
    return compute_order_total(items, tax_rate=tax)
