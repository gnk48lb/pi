"""Business rules.  No SQL here, no HTTP here."""
import time

from .errors import Conflict, Invalid


def _text(value, what):
    if not isinstance(value, str) or not value.strip():
        raise Invalid("%s is required" % what)
    return value.strip()


def _int(value, what, minimum):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise Invalid("%s must be an integer >= %d" % (what, minimum))
    return value


class BookService:
    def __init__(self, repo):
        self.repo = repo

    def add_book(self, isbn, title, author, price_cents, stock=0):
        isbn = _text(isbn, "isbn")
        title = _text(title, "title")
        author = _text(author, "author")
        price_cents = _int(price_cents, "price_cents", 0)
        stock = _int(stock, "stock", 0)
        if self.repo.find_by_isbn(isbn) is not None:
            raise Conflict("isbn already exists: %s" % isbn)
        return self.repo.add(isbn, title, author, price_cents, stock)

    def get_book(self, book_id):
        return self.repo.get(book_id)

    def list_books(self, author=None, include_deleted=False):
        return self.repo.list(author=author, include_deleted=include_deleted)

    def restock(self, book_id, amount):
        amount = _int(amount, "amount", 1)
        book = self.repo.get(book_id)
        self.repo.set_stock(book_id, book["stock"] + amount)
        return self.repo.get(book_id)

    def remove_book(self, book_id):
        self.repo.delete(book_id)

    def restore_book(self, book_id):
        return self.repo.restore(book_id)


class OrderService:
    def __init__(self, books, orders, clock=time.time):
        self.books = books
        self.orders = orders
        self.clock = clock

    def place(self, book_id, quantity):
        quantity = _int(quantity, "quantity", 1)
        book = self.books.get_book(book_id)
        if book["stock"] < quantity:
            raise Conflict("not enough stock: %d left" % book["stock"])
        self.books.repo.set_stock(book_id, book["stock"] - quantity)
        created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock()))
        order_id = self.orders.add(book_id, quantity, book["price_cents"], created)
        return {"id": order_id, "book_id": book_id, "quantity": quantity,
                "unit_price_cents": book["price_cents"], "created_at": created}

    def history(self):
        return self.orders.list()
