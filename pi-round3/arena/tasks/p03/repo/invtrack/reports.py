"""Reports over a list of orders."""
from .pricing import calc_total


def sales_report(orders, tax=0.0):
    """Return [(order_id, total)] with the biggest order first (ties by id)."""
    rows = [(o["id"], calc_total(o["items"], tax=tax)) for o in orders]
    return sorted(rows, key=lambda r: (-r[1], r[0]))


def revenue_by_category(orders, tax=0.0):
    """Return {category: revenue}, categories in alphabetical order."""
    out = {}
    for order in orders:
        for item in order["items"]:
            out[item["category"]] = out.get(item["category"], 0.0) + calc_total([item], tax=tax)
    return {k: round(v, 2) for k, v in sorted(out.items())}


def grand_total(orders, tax=0.0):
    return round(sum(calc_total(o["items"], tax) for o in orders), 2)
