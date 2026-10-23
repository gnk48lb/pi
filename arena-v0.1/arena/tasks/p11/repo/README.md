# bookshop

The backend of a small online bookstore: books with stock, and orders. Layers, from the bottom:

| file | job |
| --- | --- |
| `bookshop/migrations/NNN_*.sql` + `bookshop/db.py` | schema and the migration runner |
| `bookshop/repo.py` | all SQL (`BookRepo`, `OrderRepo`) |
| `bookshop/service.py` | business rules and validation |
| `bookshop/api.py` | `handle(shop, method, path, query, body) -> (status, payload)` |
| `bookshop/app.py` | `create_app(path)` opens the database, migrates it and returns a `Shop` |

```python
from bookshop.app import create_app
from bookshop import api

shop = create_app("shop.sqlite3")
api.handle(shop, "POST", "/books", body={"isbn": "978-1", "title": "Dune", "author": "Herbert", "price_cents": 999, "stock": 3})
api.handle(shop, "GET", "/books", query={"author": "Herbert"})
```

## API

| request | success | errors |
| --- | --- | --- |
| `GET /books` (`?author=`) | `200` list of books ordered by id | |
| `POST /books` `{isbn, title, author, price_cents, stock?}` | `201` the book | `400` invalid input, `409` ISBN already exists |
| `GET /books/<id>` | `200` the book | `404` |
| `DELETE /books/<id>` | `200 {"deleted": <id>}` | `404` |
| `POST /books/<id>/stock` `{amount}` | `200` the book with its new stock | `400`, `404` |
| `POST /orders` `{book_id, quantity}` | `201` the order | `400`, `404` unknown book, `409` not enough stock |
| `GET /orders` | `200` list of orders (with the book's `title`) ordered by id | |

A book is `{id, isbn, title, author, price_cents, stock}`.

## Database changes

Deployed databases are migrated in place when the app starts, so a schema change is always a **new** numbered file in
`bookshop/migrations/` (the next free `NNN`); migrations that were already released are never edited. The runner puts
every migration in a transaction (no `BEGIN`/`COMMIT` inside) and records it in `schema_migrations`.

## Tests

`python3 -m unittest`
