"""The HTTP-style layer: handle(shop, method, path, query, body) -> (status, payload).

Query values are strings, as they come from a URL; the body is a dict (already decoded JSON)."""
from .errors import Invalid, NotFound, ShopError


def handle(shop, method, path, query=None, body=None):
    parts = [p for p in path.strip("/").split("/") if p]
    try:
        return _route(shop, method.upper(), parts, query or {}, body or {})
    except ShopError as err:
        return err.status, {"error": str(err)}


def _book_id(text):
    try:
        return int(text)
    except ValueError:
        raise NotFound("no book %s" % text)


def _route(shop, method, parts, query, body):
    if parts == ["books"]:
        if method == "GET":
            return 200, shop.books.list_books(author=query.get("author"))
        if method == "POST":
            book = shop.books.add_book(body.get("isbn"), body.get("title"), body.get("author"),
                                       body.get("price_cents"), body.get("stock", 0))
            return 201, book
    elif len(parts) == 2 and parts[0] == "books":
        book_id = _book_id(parts[1])
        if method == "GET":
            return 200, shop.books.get_book(book_id)
        if method == "DELETE":
            shop.books.remove_book(book_id)
            return 200, {"deleted": book_id}
    elif len(parts) == 3 and parts[0] == "books" and parts[2] == "stock" and method == "POST":
        return 200, shop.books.restock(_book_id(parts[1]), body.get("amount"))
    elif parts == ["orders"]:
        if method == "GET":
            return 200, shop.orders.history()
        if method == "POST":
            if "book_id" not in body:
                raise Invalid("book_id is required")
            return 201, shop.orders.place(body["book_id"], body.get("quantity"))
    return 404, {"error": "no such route: %s /%s" % (method, "/".join(parts))}
