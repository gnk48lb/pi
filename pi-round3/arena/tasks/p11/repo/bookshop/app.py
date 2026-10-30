"""Wiring: one SQLite connection, the repositories and the services on top of them."""
import time

from . import db
from .repo import BookRepo, OrderRepo
from .service import BookService, OrderService


class Shop:
    """The object the API layer works with.  It does not migrate: use create_app() or db.migrate() first."""

    def __init__(self, conn, clock=None):
        self.conn = conn
        self.books = BookService(BookRepo(conn))
        self.orders = OrderService(self.books, OrderRepo(conn), clock or time.time)


def create_app(path=":memory:", clock=None):
    """Open (or create) the database at `path`, bring it to the latest schema and return a Shop."""
    conn = db.connect(path)
    db.migrate(conn)
    return Shop(conn, clock)
