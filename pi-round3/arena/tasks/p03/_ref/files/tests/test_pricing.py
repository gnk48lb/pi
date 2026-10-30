import unittest

import warnings

from invtrack.pricing import calc_total, compute_order_total, line_total


class PricingTests(unittest.TestCase):
    def test_line_total(self):
        self.assertEqual(line_total({"price": 2.5, "qty": 4}), 10.0)

    def test_total_without_tax(self):
        items = [{"price": 10.0, "qty": 2}, {"price": 0.5, "qty": 3}]
        self.assertEqual(compute_order_total(items), 21.5)

    def test_total_with_tax(self):
        items = [{"price": 10.0, "qty": 2}]
        self.assertEqual(compute_order_total(items, tax_rate=0.2), 24.0)

    def test_total_rounds_to_cents(self):
        self.assertEqual(compute_order_total([{"price": 0.333, "qty": 1}], 0.1), 0.37)

    def test_empty_order(self):
        self.assertEqual(compute_order_total([]), 0.0)


class DeprecatedAliasTests(unittest.TestCase):
    def test_calc_total_still_works_and_warns(self):
        items = [{"price": 10.0, "qty": 2}]
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(calc_total(items, tax=0.2), 24.0)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.assertEqual(calc_total(items, 0.5), 30.0)
        self.assertEqual(len(caught), 1)
        self.assertIn("compute_order_total", str(caught[0].message))
