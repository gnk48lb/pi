import os
import shutil
import tempfile
import unittest

from bookshop import api, db
from bookshop.app import Shop, create_app


def call(shop, method, path, query=None, body=None):
    return api.handle(shop, method, path, query, body)


class SoftDeleteTests(unittest.TestCase):
    def setUp(self):
        self.shop = create_app(":memory:")

    def add(self, isbn="1", author="Herbert", stock=5):
        status, book = call(self.shop, "POST", "/books", body={
            "isbn": isbn, "title": "Dune", "author": author, "price_cents": 999, "stock": stock})
        self.assertEqual(status, 201, book)
        return book

    def test_delete_hides_the_book(self):
        book = self.add()
        self.assertEqual(call(self.shop, "DELETE", "/books/%d" % book["id"]), (200, {"deleted": book["id"]}))
        self.assertEqual(call(self.shop, "GET", "/books/%d" % book["id"])[0], 404)
        self.assertEqual(call(self.shop, "GET", "/books")[1], [])
        self.assertEqual(call(self.shop, "DELETE", "/books/%d" % book["id"])[0], 404)

    def test_book_with_orders_can_be_deleted_and_orders_stay(self):
        book = self.add()
        call(self.shop, "POST", "/orders", body={"book_id": book["id"], "quantity": 1})
        self.assertEqual(call(self.shop, "DELETE", "/books/%d" % book["id"])[0], 200)
        orders = call(self.shop, "GET", "/orders")[1]
        self.assertEqual([o["title"] for o in orders], ["Dune"])
        self.assertEqual(call(self.shop, "POST", "/orders", body={"book_id": book["id"], "quantity": 1})[0], 404)

    def test_include_deleted(self):
        a, b = self.add(isbn="1"), self.add(isbn="2")
        call(self.shop, "DELETE", "/books/%d" % b["id"])
        live = call(self.shop, "GET", "/books")[1]
        everything = call(self.shop, "GET", "/books", query={"include_deleted": "1"})[1]
        self.assertEqual([x["id"] for x in live], [a["id"]])
        self.assertEqual([(x["id"], x["deleted"]) for x in everything], [(a["id"], False), (b["id"], True)])

    def test_restore(self):
        book = self.add()
        call(self.shop, "DELETE", "/books/%d" % book["id"])
        status, restored = call(self.shop, "POST", "/books/%d/restore" % book["id"])
        self.assertEqual((status, restored["id"], restored["deleted"]), (200, book["id"], False))
        self.assertEqual(call(self.shop, "POST", "/books/%d/restore" % book["id"])[0], 409)
        self.assertEqual(call(self.shop, "POST", "/books/99/restore")[0], 404)

    def test_isbn_is_unique_among_live_books_only(self):
        first = self.add(isbn="X")
        call(self.shop, "DELETE", "/books/%d" % first["id"])
        second = self.add(isbn="X")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(call(self.shop, "POST", "/books", body={
            "isbn": "X", "title": "T", "author": "A", "price_cents": 1})[0], 409)
        self.assertEqual(call(self.shop, "POST", "/books/%d/restore" % first["id"])[0], 409)

    def test_existing_database_is_upgraded_in_place(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        conn = db.connect(os.path.join(tmp, "old.sqlite3"))
        db.migrate(conn, target=2)
        conn.execute("INSERT INTO books (isbn, title, author, price_cents, stock) VALUES ('A', 'Old', 'Ann', 100, 2)")
        conn.commit()
        self.assertEqual(db.migrate(conn)[0], 3)
        shop = Shop(conn)
        books = call(shop, "GET", "/books")[1]
        self.assertEqual([(b["title"], b["deleted"]) for b in books], [("Old", False)])


if __name__ == "__main__":
    unittest.main()
