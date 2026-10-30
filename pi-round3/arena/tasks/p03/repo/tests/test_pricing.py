import unittest

from invtrack.pricing import calc_total, line_total


class PricingTests(unittest.TestCase):
    def test_line_total(self):
        self.assertEqual(line_total({"price": 2.5, "qty": 4}), 10.0)

    def test_total_without_tax(self):
        items = [{"price": 10.0, "qty": 2}, {"price": 0.5, "qty": 3}]
        self.assertEqual(calc_total(items), 21.5)

    def test_total_with_tax(self):
        items = [{"price": 10.0, "qty": 2}]
        self.assertEqual(calc_total(items, tax=0.2), 24.0)

    def test_total_rounds_to_cents(self):
        self.assertEqual(calc_total([{"price": 0.333, "qty": 1}], 0.1), 0.37)

    def test_empty_order(self):
        self.assertEqual(calc_total([]), 0.0)
