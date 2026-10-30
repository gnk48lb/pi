import unittest

from bookshop import api
from bookshop.app import create_app


def call(shop, method, path, query=None, body=None):
    return api.handle(shop, method, path, query, body)


class OrderApiTests(unittest.TestCase):
    def setUp(self):
        self.shop = create_app(":memory:", clock=lambda: 1_700_000_000)
        status, self.book = call(self.shop, "POST", "/books", body={
            "isbn": "978-1", "title": "Dune", "author": "Herbert", "price_cents": 999, "stock": 5})
        self.assertEqual(status, 201)

    def order(self, quantity):
        return call(self.shop, "POST", "/orders", body={"book_id": self.book["id"], "quantity": quantity})

    def test_place_order_reduces_stock(self):
        status, order = self.order(2)
        self.assertEqual(status, 201)
        self.assertEqual((order["quantity"], order["unit_price_cents"]), (2, 999))
        self.assertEqual(call(self.shop, "GET", "/books/%d" % self.book["id"])[1]["stock"], 3)

    def test_not_enough_stock(self):
        self.assertEqual(self.order(6)[0], 409)
        self.assertEqual(call(self.shop, "GET", "/books/%d" % self.book["id"])[1]["stock"], 5)

    def test_unknown_book(self):
        status, body = call(self.shop, "POST", "/orders", body={"book_id": 42, "quantity": 1})
        self.assertEqual(status, 404)

    def test_history_has_the_title(self):
        self.order(1)
        self.order(2)
        status, orders = call(self.shop, "GET", "/orders")
        self.assertEqual(status, 200)
        self.assertEqual([(o["title"], o["quantity"]) for o in orders], [("Dune", 1), ("Dune", 2)])
        self.assertEqual(orders[0]["created_at"], "2023-11-14T22:13:20Z")


if __name__ == "__main__":
    unittest.main()
