"""Cart discounts.  All money is integer cents.  See README.md for the rules."""

RULE_TYPES = ("percent", "fixed", "bogo", "cap")


def _validate(cart, rules):
    for line in cart:
        if line["unit_cents"] < 0:
            raise ValueError("negative quantity or price for %r" % (line["sku"],))
    for index, rule in enumerate(rules):
        kind = rule.get("type")
        if kind not in RULE_TYPES:
            raise ValueError("rule %d: unknown type %r" % (index, kind))
        if kind == "percent" and not 0 <= rule["value"] <= 100:
            raise ValueError("rule %d: percent must be between 0 and 100" % index)
        if kind == "fixed" and rule["value"] < 0:
            raise ValueError("rule %d: a fixed discount must not be negative" % index)
        if kind == "cap" and not 0 <= rule["max_percent"] <= 100:
            raise ValueError("rule %d: max_percent must be between 0 and 100" % index)


def apply_discounts(cart, rules):
    _validate(cart, rules)
    subtotal = sum(line["unit_cents"] * line["qty"] for line in cart)
    amounts = [line["unit_cents"] * line["qty"] for line in cart]
    given = [0] * len(rules)

    for index, rule in enumerate(rules):                       # 1. buy one get one
        if rule["type"] != "bogo":
            continue
        for n, line in enumerate(cart):
            if line["sku"] == rule["sku"]:
                cut = min(amounts[n], (line["qty"] // 2) * line["unit_cents"])
                amounts[n] -= cut
                given[index] += cut

    for index, rule in enumerate(rules):                       # 2. percentages, one after the other
        if rule["type"] != "percent":
            continue
        for n, line in enumerate(cart):
            if rule.get("category") is None or line.get("category") == rule["category"]:
                cut = (amounts[n] * rule["value"] + 50) // 100
                amounts[n] -= cut
                given[index] += cut

    remaining = sum(amounts)
    for index, rule in enumerate(rules):                       # 3. fixed amounts
        if rule["type"] != "fixed":
            continue
        if subtotal >= rule.get("min_subtotal", 0):
            cut = min(remaining, rule["value"])
            remaining -= cut
            given[index] += cut

    discount = sum(given)
    limits = [subtotal * rule["max_percent"] // 100 for rule in rules if rule["type"] == "cap"]   # 4. cap
    if limits:
        discount = min(discount, min(limits))

    return {
        "subtotal": subtotal,
        "discount": discount,
        "total": subtotal - discount,
        "applied": [(index, cents) for index, cents in enumerate(given) if cents > 0],
    }
