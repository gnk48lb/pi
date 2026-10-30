import unittest

from shopcore.pricing import price_bulk, price_for


class PricingTests(unittest.TestCase):
    def test_price_for_in_euro(self):
        self.assertEqual(price_for("A-1", 2, currency="EUR"), 2500)

    def test_price_for_converts_to_the_requested_currency(self):
        self.assertEqual(price_for("A-1", 3, currency="USD"), 4125)
        self.assertEqual(price_for("D-4", 3, currency="GBP"), 13)

    def test_price_bulk_uses_the_best_tier(self):
        self.assertEqual(price_bulk("A-1", 10, currency="EUR"), 11000)
        self.assertEqual(price_bulk("A-1", 9, currency="EUR"), 11250)

    def test_unknown_currency(self):
        with self.assertRaises(ValueError):
            price_for("A-1", 1, currency="XXX")


if __name__ == "__main__":
    unittest.main()
