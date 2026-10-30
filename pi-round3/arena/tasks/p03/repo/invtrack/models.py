"""Plain data helpers for items and orders."""


def make_item(sku, price, qty=1, category="general"):
    return {"sku": sku, "price": float(price), "qty": int(qty), "category": category}


def validate_item(item):
    for key in ("sku", "price", "qty"):
        if key not in item:
            raise ValueError("item is missing %r" % key)
    if item["qty"] < 0 or item["price"] < 0:
        raise ValueError("negative price or quantity in %r" % item["sku"])
    item.setdefault("category", "general")
    return item


def validate_order(order):
    if "id" not in order or "items" not in order:
        raise ValueError("order needs an id and items")
    order["items"] = [validate_item(i) for i in order["items"]]
    return order
