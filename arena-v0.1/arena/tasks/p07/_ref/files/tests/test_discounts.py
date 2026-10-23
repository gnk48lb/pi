import unittest

from discounts import apply_discounts


def line(sku, unit, qty, category=None):
    d = {"sku": sku, "unit_cents": unit, "qty": qty}
    if category is not None:
        d["category"] = category
    return d


class ResultShape(unittest.TestCase):
    def test_no_rules(self):
        r = apply_discounts([line("A", 100, 2), line("B", 50, 1)], [])
        self.assertEqual(r, {"subtotal": 250, "discount": 0, "total": 250, "applied": []})

    def test_empty_cart(self):
        self.assertEqual(apply_discounts([], [{"type": "fixed", "value": 100}]),
                         {"subtotal": 0, "discount": 0, "total": 0, "applied": []})

    def test_readme_example(self):
        cart = [line("A", 1000, 3, "book"), line("B", 250, 2)]
        rules = [{"type": "bogo", "sku": "A"}, {"type": "percent", "value": 10, "category": "book"},
                 {"type": "fixed", "value": 500, "min_subtotal": 3000}, {"type": "cap", "max_percent": 30}]
        self.assertEqual(apply_discounts(cart, rules),
                         {"subtotal": 3500, "discount": 1050, "total": 2450, "applied": [(0, 1000), (1, 200), (2, 500)]})

    def test_applied_lists_only_rules_that_gave_something_in_rule_order(self):
        cart = [line("A", 100, 1, "x")]
        rules = [{"type": "percent", "value": 10, "category": "other"}, {"type": "fixed", "value": 5},
                 {"type": "bogo", "sku": "A"}, {"type": "percent", "value": 50}]
        r = apply_discounts(cart, rules)
        self.assertEqual(r["applied"], [(1, 5), (3, 50)])


class Bogo(unittest.TestCase):
    def test_every_second_item_is_free(self):
        for qty, free in ((1, 0), (2, 1), (3, 1), (4, 2), (5, 2)):
            r = apply_discounts([line("A", 100, qty)], [{"type": "bogo", "sku": "A"}])
            self.assertEqual(r["discount"], 100 * free, qty)

    def test_only_the_named_sku(self):
        r = apply_discounts([line("A", 100, 2), line("B", 70, 2)], [{"type": "bogo", "sku": "B"}])
        self.assertEqual(r["discount"], 70)


class Percent(unittest.TestCase):
    def test_rounds_half_up(self):
        # 1005 * 15 / 100 = 150.75 -> 151 ; 10 * 15 / 100 = 1.5 -> 2 ; 30 * 15 / 100 = 4.5 -> 5 ; 9 * 10 / 100 = 0.9 -> 1
        for unit, pct, want in ((1005, 15, 151), (10, 15, 2), (30, 15, 5), (9, 10, 1), (4, 10, 0)):
            r = apply_discounts([line("A", unit, 1)], [{"type": "percent", "value": pct}])
            self.assertEqual(r["discount"], want, (unit, pct))

    def test_rounding_is_per_line(self):
        r = apply_discounts([line("A", 15, 1), line("B", 15, 1)], [{"type": "percent", "value": 10}])
        self.assertEqual(r["discount"], 4)           # 2 + 2 (1.5 rounds up on each line), not 3

    def test_category_filter(self):
        cart = [line("A", 1000, 1, "book"), line("B", 1000, 1, "toy"), line("C", 1000, 1)]
        r = apply_discounts(cart, [{"type": "percent", "value": 10, "category": "book"}])
        self.assertEqual(r["discount"], 100)

    def test_without_category_every_line_matches(self):
        cart = [line("A", 1000, 1, "book"), line("B", 1000, 1, "toy"), line("C", 1000, 1)]
        self.assertEqual(apply_discounts(cart, [{"type": "percent", "value": 10}])["discount"], 300)

    def test_percent_rules_stack_one_after_the_other(self):
        r = apply_discounts([line("A", 1000, 1)], [{"type": "percent", "value": 10}, {"type": "percent", "value": 10}])
        self.assertEqual(r["discount"], 190)
        self.assertEqual(r["applied"], [(0, 100), (1, 90)])

    def test_percent_applies_to_what_bogo_left(self):
        r = apply_discounts([line("A", 1000, 2)], [{"type": "percent", "value": 10}, {"type": "bogo", "sku": "A"}])
        self.assertEqual(r["discount"], 1000 + 100)
        self.assertEqual(r["applied"], [(0, 100), (1, 1000)])

    def test_hundred_percent(self):
        r = apply_discounts([line("A", 333, 3)], [{"type": "percent", "value": 100}])
        self.assertEqual(r["total"], 0)


class Fixed(unittest.TestCase):
    def test_simple(self):
        r = apply_discounts([line("A", 1000, 1)], [{"type": "fixed", "value": 250}])
        self.assertEqual((r["discount"], r["total"]), (250, 750))

    def test_min_subtotal_is_inclusive(self):
        rule = [{"type": "fixed", "value": 100, "min_subtotal": 1000}]
        self.assertEqual(apply_discounts([line("A", 1000, 1)], rule)["discount"], 100)
        self.assertEqual(apply_discounts([line("A", 999, 1)], rule)["discount"], 0)

    def test_threshold_uses_the_original_subtotal(self):
        cart = [line("A", 1000, 1)]
        rules = [{"type": "percent", "value": 50}, {"type": "fixed", "value": 100, "min_subtotal": 800}]
        self.assertEqual(apply_discounts(cart, rules)["discount"], 600)

    def test_never_takes_the_cart_below_zero(self):
        r = apply_discounts([line("A", 300, 1)], [{"type": "fixed", "value": 500}])
        self.assertEqual((r["discount"], r["total"]), (300, 0))
        self.assertEqual(r["applied"], [(0, 300)])

    def test_clamp_is_on_what_is_left_after_percent(self):
        r = apply_discounts([line("A", 1000, 1)], [{"type": "percent", "value": 90}, {"type": "fixed", "value": 500}])
        self.assertEqual((r["discount"], r["total"]), (1000, 0))


class Cap(unittest.TestCase):
    def test_limits_the_total_discount(self):
        r = apply_discounts([line("A", 1000, 1)], [{"type": "percent", "value": 80}, {"type": "cap", "max_percent": 30}])
        self.assertEqual((r["discount"], r["total"]), (300, 700))

    def test_limit_rounds_down(self):
        r = apply_discounts([line("A", 1001, 1)], [{"type": "percent", "value": 80}, {"type": "cap", "max_percent": 30}])
        self.assertEqual(r["discount"], 300)           # 300.3 -> 300

    def test_smallest_of_several_caps_wins(self):
        r = apply_discounts([line("A", 1000, 1)], [{"type": "percent", "value": 80}, {"type": "cap", "max_percent": 50},
                                                    {"type": "cap", "max_percent": 20}, {"type": "cap", "max_percent": 40}])
        self.assertEqual(r["discount"], 200)

    def test_cap_does_not_raise_the_discount(self):
        r = apply_discounts([line("A", 1000, 1)], [{"type": "percent", "value": 10}, {"type": "cap", "max_percent": 50}])
        self.assertEqual(r["discount"], 100)

    def test_applied_shows_what_the_rules_gave_before_the_cap(self):
        r = apply_discounts([line("A", 1000, 1)], [{"type": "percent", "value": 80}, {"type": "cap", "max_percent": 30}])
        self.assertEqual(r["applied"], [(0, 800)])


class Validation(unittest.TestCase):
    def check(self, cart, rules):
        with self.assertRaises(ValueError):
            apply_discounts(cart, rules)

    def test_negative_quantity_or_price(self):
        self.check([line("A", 100, -1)], [])
        self.check([line("A", -100, 1)], [])

    def test_unknown_rule_type(self):
        self.check([line("A", 100, 1)], [{"type": "coupon", "value": 5}])

    def test_percent_out_of_range(self):
        self.check([line("A", 100, 1)], [{"type": "percent", "value": 101}])
        self.check([line("A", 100, 1)], [{"type": "percent", "value": -1}])

    def test_negative_fixed(self):
        self.check([line("A", 100, 1)], [{"type": "fixed", "value": -5}])

    def test_cap_out_of_range(self):
        self.check([line("A", 100, 1)], [{"type": "cap", "max_percent": 101}])
        self.check([line("A", 100, 1)], [{"type": "cap", "max_percent": -1}])

    def test_rules_are_validated_for_an_empty_cart_too(self):
        self.check([], [{"type": "nope"}])


if __name__ == "__main__":
    unittest.main()
