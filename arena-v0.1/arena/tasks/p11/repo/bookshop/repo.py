"""SQL lives here and only here."""
import sqlite3

from .errors import Conflict, NotFound

BOOK_COLUMNS = "id, isbn, title, author, price_cents, stock"


class BookRepo:
    def __init__(self, conn):
        self.conn = conn

    def add(self, isbn, title, author, price_cents, stock):
        try:
            with self.conn:
                cur = self.conn.execute(
                    "INSERT INTO books (isbn, title, author, price_cents, stock) VALUES (?, ?, ?, ?, ?)",
                    (isbn, title, author, price_cents, stock))
        except sqlite3.IntegrityError:
            raise Conflict("isbn already exists: %s" % isbn)
        return self.get(cur.lastrowid)

    def get(self, book_id):
        row = self.conn.execute("SELECT %s FROM books WHERE id = ?" % BOOK_COLUMNS, (book_id,)).fetchone()
        if row is None:
            raise NotFound("no book %s" % book_id)
        return dict(row)

    def find_by_isbn(self, isbn):
        row = self.conn.execute("SELECT %s FROM books WHERE isbn = ?" % BOOK_COLUMNS, (isbn,)).fetchone()
        return dict(row) if row is not None else None

    def list(self, author=None):
        sql = "SELECT %s FROM books" % BOOK_COLUMNS
        args = []
        if author is not None:
            sql += " WHERE author = ?"
            args.append(author)
        sql += " ORDER BY id"
        return [dict(row) for row in self.conn.execute(sql, args)]

    def set_stock(self, book_id, stock):
        with self.conn:
            cur = self.conn.execute("UPDATE books SET stock = ? WHERE id = ?", (stock, book_id))
        if cur.rowcount == 0:
            raise NotFound("no book %s" % book_id)

    def delete(self, book_id):
        with self.conn:
            cur = self.conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
        if cur.rowcount == 0:
            raise NotFound("no book %s" % book_id)


class OrderRepo:
    def __init__(self, conn):
        self.conn = conn

    def add(self, book_id, quantity, unit_price_cents, created_at):
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO orders (book_id, quantity, unit_price_cents, created_at) VALUES (?, ?, ?, ?)",
                (book_id, quantity, unit_price_cents, created_at))
        return cur.lastrowid

    def list(self):
        rows = self.conn.execute(
            "SELECT o.id, o.book_id, b.title AS title, o.quantity, o.unit_price_cents, o.created_at "
            "FROM orders o JOIN books b ON b.id = o.book_id ORDER BY o.id")
        return [dict(row) for row in rows]
