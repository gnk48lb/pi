from . import pricing


def export_rows(orders, mode="for"):
    """One 'number,sku,qty,cents' row per order line; `mode` picks the pricing function ('for' or 'bulk')."""
    price = getattr(pricing, "price_" + mode)
    rows = []
    for order in orders:
        for sku, qty in order.lines:
            rows.append("%s,%s,%d,%d" % (order.number, sku, qty, price(sku, qty)))
    return rows
