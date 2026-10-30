import unittest

from shopcore import Cart


class CartTests(unittest.TestCase):
    def test_euro_cart(self):
        cart = Cart("EUR")
        cart.add("A-1", 2)
        cart.add("B-2")
        self.assertEqual(cart.total(), 2500 + 799)

    def test_a_usd_cart_is_priced_in_usd(self):
        cart = Cart("USD")
        cart.add("A-1", 2)
        self.assertEqual(cart.total(), 2750)

    def test_a_gbp_cart_is_priced_in_gbp(self):
        cart = Cart("GBP")
        cart.add("C-3")
        self.assertEqual(cart.total(), 12750)


if __name__ == "__main__":
    unittest.main()
