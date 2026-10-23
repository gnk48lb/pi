"""CSV export."""
import csv
import io

from .pricing import compute_order_total
from .utils import money


def to_csv(orders, tax=0.0):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["id", "items", "total"])
    for order in orders:
        writer.writerow([order["id"], len(order["items"]), money(compute_order_total(order["items"], tax))])
    return buf.getvalue()
