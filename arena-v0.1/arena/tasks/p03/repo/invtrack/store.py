"""Reading and writing order files."""
import json

from .models import validate_order


def load_orders(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return [validate_order(o) for o in data["orders"]]


def save_orders(path, orders):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"orders": orders}, fh, indent=2, sort_keys=True)
        fh.write("\n")
