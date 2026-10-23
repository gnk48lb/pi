"""Hidden acceptance tests of p11 (soft delete of books)."""
import os
import shutil
import tempfile
import unittest

from bookshop import api, db
from bookshop.app import Shop, create_app


def call(shop, method, path, query=None, body=None):
    return api.handle(shop, method, path, query, body)


class Spec(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.shop = create_app(":memory:", clock=lambda: 1_700_000_000)

    def add(self, isbn="978-1", title="Dune", author="Herbert", price_cents=999, stock=5, shop=None):
        status, book = call(shop or self.shop, "POST", "/books", body={
            "isbn": isbn, "title": title, "author": author, "price_cents": price_cents, "stock": stock})
        self.assertEqual(status, 201, book)
        return book

    def delete(self, book):
        return call(self.shop, "DELETE", "/books/%d" % book["id"])

    def order(self, book, quantity=1):
        return call(self.shop, "POST", "/orders", body={"book_id": book["id"], "quantity": quantity})

    def ids(self, books):
        return [b["id"] for b in books]

    # ------------------------------------------------------------------ deleting
    def test_delete_is_soft_and_hides_the_book(self):
        book = self.add()
        self.assertEqual(self.delete(book), (200, {"deleted": book["id"]}))
        self.assertEqual(call(self.shop, "GET", "/books/%d" % book["id"])[0], 404)
        self.assertEqual(call(self.shop, "GET", "/books"), (200, []))
        self.assertEqual(call(self.shop, "GET", "/books", query={"author": "Herbert"}), (200, []))

    def test_delete_unknown_or_already_deleted_is_404(self):
        book = self.add()
        self.assertEqual(call(self.shop, "DELETE", "/books/999")[0], 404)
        self.assertEqual(self.delete(book)[0], 200)
        self.assertEqual(self.delete(book)[0], 404)

    def test_book_with_orders_can_be_deleted(self):
        book = self.add()
        self.assertEqual(self.order(book, 2)[0], 201)
        self.assertEqual(self.delete(book), (200, {"deleted": book["id"]}))

    def test_orders_keep_showing_deleted_books(self):
        book = self.add(title="Dune")
        other = self.add(isbn="978-2", title="Emma")
        self.order(book, 1)
        self.order(other, 2)
        self.delete(book)
        status, orders = call(self.shop, "GET", "/orders")
        self.assertEqual(status, 200)
        self.assertEqual([(o["title"], o["quantity"]) for o in orders], [("Dune", 1), ("Emma", 2)])

    def test_deleted_book_cannot_be_ordered_or_restocked(self):
        book = self.add()
        self.delete(book)
        self.assertEqual(self.order(book)[0], 404)
        self.assertEqual(call(self.shop, "POST", "/books/%d/stock" % book["id"], body={"amount": 3})[0], 404)

    # ------------------------------------------------------------------ listing
    def test_include_deleted_listing(self):
        b1 = self.add(isbn="1", author="Herbert")
        b2 = self.add(isbn="2", author="Le Guin")
        b3 = self.add(isbn="3", author="Herbert")
        self.delete(b3)
        self.assertEqual(self.ids(call(self.shop, "GET", "/books")[1]), [b1["id"], b2["id"]])
        for flag in ("1", "true"):
            status, books = call(self.shop, "GET", "/books", query={"include_deleted": flag})
            self.assertEqual(status, 200)
            self.assertEqual(self.ids(books), [b1["id"], b2["id"], b3["id"]], flag)
            self.assertEqual([b["deleted"] for b in books], [False, False, True])
        self.assertEqual(self.ids(call(self.shop, "GET", "/books", query={"include_deleted": "0"})[1]),
                         [b1["id"], b2["id"]])
        self.assertEqual(self.ids(call(self.shop, "GET", "/books", query={"author": "Herbert"})[1]), [b1["id"]])
        self.assertEqual(self.ids(call(self.shop, "GET", "/books", query={"author": "Herbert", "include_deleted": "1"})[1]),
                         [b1["id"], b3["id"]])
        self.assertEqual(self.ids(call(self.shop, "GET", "/books", query={"author": "Le Guin", "include_deleted": "1"})[1]),
                         [b2["id"]])

    def test_every_book_has_a_boolean_deleted_field(self):
        book = self.add()
        self.assertIs(book["deleted"], False)
        self.assertIs(call(self.shop, "GET", "/books/%d" % book["id"])[1]["deleted"], False)
        self.assertIs(call(self.shop, "GET", "/books")[1][0]["deleted"], False)
        self.assertIs(call(self.shop, "POST", "/books/%d/stock" % book["id"], body={"amount": 1})[1]["deleted"], False)
        self.delete(book)
        everything = call(self.shop, "GET", "/books", query={"include_deleted": "1"})[1]
        self.assertIs(everything[0]["deleted"], True)
        restored = call(self.shop, "POST", "/books/%d/restore" % book["id"])[1]
        self.assertIs(restored["deleted"], False)

    # ------------------------------------------------------------------ restoring
    def test_restore_brings_the_book_back_unchanged(self):
        book = self.add(stock=5)
        self.order(book, 2)
        self.delete(book)
        status, restored = call(self.shop, "POST", "/books/%d/restore" % book["id"])
        self.assertEqual(status, 200)
        self.assertEqual((restored["id"], restored["isbn"], restored["title"], restored["stock"]),
                         (book["id"], "978-1", "Dune", 3))
        self.assertEqual(call(self.shop, "GET", "/books/%d" % book["id"])[0], 200)
        self.assertEqual(self.ids(call(self.shop, "GET", "/books")[1]), [book["id"]])
        self.assertEqual(self.order(book, 1)[0], 201)

    def test_restore_errors(self):
        book = self.add()
        self.assertEqual(call(self.shop, "POST", "/books/999/restore")[0], 404)
        self.assertEqual(call(self.shop, "POST", "/books/abc/restore")[0], 404)
        self.assertEqual(call(self.shop, "POST", "/books/%d/restore" % book["id"])[0], 409)     # not deleted

    # ------------------------------------------------------------------ ISBN uniqueness
    def test_isbn_can_be_reused_after_delete(self):
        first = self.add(isbn="X-1", title="First")
        self.delete(first)
        second = self.add(isbn="X-1", title="Second")
        self.assertNotEqual(first["id"], second["id"])
        status, body = call(self.shop, "POST", "/books", body={
            "isbn": "X-1", "title": "Third", "author": "A", "price_cents": 1})
        self.assertEqual(status, 409, body)

    def test_restore_conflicts_with_a_live_book_of_the_same_isbn(self):
        first = self.add(isbn="X-1", title="First")
        self.delete(first)
        second = self.add(isbn="X-1", title="Second")
        self.assertEqual(call(self.shop, "POST", "/books/%d/restore" % first["id"])[0], 409)
        self.assertEqual(self.delete(second)[0], 200)
        self.assertEqual(call(self.shop, "POST", "/books/%d/restore" % first["id"])[0], 200)
        self.assertEqual([b["title"] for b in call(self.shop, "GET", "/books")[1]], ["First"])

    # ------------------------------------------------------------------ persistence and migration
    def test_soft_delete_is_stored_in_the_database(self):
        path = os.path.join(self.tmp, "shop.sqlite3")
        shop = create_app(path)
        book = self.add(shop=shop, isbn="P-1")
        self.assertEqual(call(shop, "DELETE", "/books/%d" % book["id"])[0], 200)
        shop.conn.close()
        again = create_app(path)
        self.assertEqual(call(again, "GET", "/books"), (200, []))
        everything = call(again, "GET", "/books", query={"include_deleted": "1"})[1]
        self.assertEqual([(b["isbn"], b["deleted"]) for b in everything], [("P-1", True)])
        self.assertEqual(call(again, "POST", "/books/%d/restore" % book["id"])[0], 200)

    def test_existing_database_is_upgraded_in_place(self):
        path = os.path.join(self.tmp, "old.sqlite3")
        conn = db.connect(path)
        self.assertEqual(db.migrate(conn, target=2), [1, 2])
        conn.execute("INSERT INTO books (isbn, title, author, price_cents, stock) VALUES ('A-1', 'Old One', 'Ann', 500, 4)")
        conn.execute("INSERT INTO books (isbn, title, author, price_cents, stock) VALUES ('B-2', 'Old Two', 'Bob', 700, 0)")
        conn.execute("INSERT INTO orders (book_id, quantity, unit_price_cents, created_at) "
                     "VALUES (1, 1, 500, '2024-01-01T00:00:00Z')")
        conn.commit()
        applied = db.migrate(conn)
        self.assertTrue(applied and applied[0] == 3, applied)
        self.assertEqual(db.migrate(conn), [])
        shop = Shop(conn)
        books = call(shop, "GET", "/books")[1]
        self.assertEqual([(b["isbn"], b["title"], b["stock"], b["deleted"]) for b in books],
                         [("A-1", "Old One", 4, False), ("B-2", "Old Two", 0, False)])
        orders = call(shop, "GET", "/orders")[1]
        self.assertEqual([(o["title"], o["quantity"]) for o in orders], [("Old One", 1)])
        self.assertEqual(call(shop, "DELETE", "/books/1"), (200, {"deleted": 1}))        # it has an order
        self.assertEqual([b["isbn"] for b in call(shop, "GET", "/books")[1]], ["B-2"])
        self.assertEqual(self.add(shop=shop, isbn="A-1", title="New One")["title"], "New One")

    def test_schema_change_is_a_new_migration(self):
        versions = [v for v, _ in db.available()]
        self.assertEqual(versions[:2], [1, 2])
        self.assertGreater(len(versions), 2)
        conn = db.connect(":memory:")
        self.assertEqual(db.migrate(conn), versions)


if __name__ == "__main__":
    unittest.main()
