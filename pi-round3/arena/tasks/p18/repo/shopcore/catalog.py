"""The product catalog. Prices are in euro cents."""

CATALOG = {
    "A-1": {"name": "Widget", "eur_cents": 1250, "bulk": [(10, 1100), (50, 950)]},
    "B-2": {"name": "Gadget", "eur_cents": 799, "bulk": [(20, 700)]},
    "C-3": {"name": "Gizmo", "eur_cents": 15000, "bulk": []},
    "D-4": {"name": "Doohickey", "eur_cents": 5, "bulk": [(100, 4)]},
}
