import unittest

from shopcore import Order, order_total


class OrderTests(unittest.TestCase):
    def test_euro_order(self):
        self.assertEqual(order_total(Order("N1", "EUR", [("A-1", 2), ("B-2", 1)])), 3299)

    def test_chf_order(self):
        self.assertEqual(order_total(Order("N2", "CHF", [("A-1", 2), ("B-2", 1)])), 3167)


if __name__ == "__main__":
    unittest.main()
