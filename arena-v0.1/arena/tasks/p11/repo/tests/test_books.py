import unittest

from bookshop import api
from bookshop.app import create_app


def call(shop, method, path, query=None, body=None):
    return api.handle(shop, method, path, query, body)


class BookApiTests(unittest.TestCase):
    def setUp(self):
        self.shop = create_app(":memory:")

    def add(self, isbn="978-1", title="Dune", author="Herbert", price_cents=999, stock=3):
        status, book = call(self.shop, "POST", "/books", body={
            "isbn": isbn, "title": title, "author": author, "price_cents": price_cents, "stock": stock})
        self.assertEqual(status, 201, book)
        return book

    def test_add_and_get(self):
        book = self.add()
        status, got = call(self.shop, "GET", "/books/%d" % book["id"])
        self.assertEqual(status, 200)
        self.assertEqual((got["isbn"], got["title"], got["stock"]), ("978-1", "Dune", 3))

    def test_list_is_ordered_by_id_and_filters_by_author(self):
        self.add(isbn="1", author="Herbert")
        self.add(isbn="2", author="Le Guin", title="Earthsea")
        self.add(isbn="3", author="Herbert", title="Children of Dune")
        status, books = call(self.shop, "GET", "/books")
        self.assertEqual([b["isbn"] for b in books], ["1", "2", "3"])
        status, books = call(self.shop, "GET", "/books", query={"author": "Herbert"})
        self.assertEqual([b["isbn"] for b in books], ["1", "3"])

    def test_duplicate_isbn_is_a_conflict(self):
        self.add(isbn="1")
        status, body = call(self.shop, "POST", "/books", body={
            "isbn": "1", "title": "Other", "author": "X", "price_cents": 1})
        self.assertEqual(status, 409)

    def test_invalid_input(self):
        status, body = call(self.shop, "POST", "/books", body={"isbn": "", "title": "T", "author": "A", "price_cents": 5})
        self.assertEqual(status, 400)
        status, body = call(self.shop, "POST", "/books", body={"isbn": "9", "title": "T", "author": "A", "price_cents": -5})
        self.assertEqual(status, 400)

    def test_restock(self):
        book = self.add(stock=2)
        status, got = call(self.shop, "POST", "/books/%d/stock" % book["id"], body={"amount": 5})
        self.assertEqual((status, got["stock"]), (200, 7))

    def test_delete_removes_the_book(self):
        book = self.add()
        status, body = call(self.shop, "DELETE", "/books/%d" % book["id"])
        self.assertEqual((status, body), (200, {"deleted": book["id"]}))
        self.assertEqual(call(self.shop, "GET", "/books/%d" % book["id"])[0], 404)
        self.assertEqual(call(self.shop, "GET", "/books")[1], [])

    def test_delete_unknown_book(self):
        self.assertEqual(call(self.shop, "DELETE", "/books/99")[0], 404)

    def test_unknown_route(self):
        self.assertEqual(call(self.shop, "GET", "/nope")[0], 404)


if __name__ == "__main__":
    unittest.main()
