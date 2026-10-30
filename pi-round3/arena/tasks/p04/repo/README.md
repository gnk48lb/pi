# shelfwise

A small in-memory bookstore API. There is no network layer: `app.handle(method, path, { query, body })`
returns `{ status, body }`, which keeps the tests fast.

```js
const { createSeededApp } = require('./src');
const app = createSeededApp();
app.handle('GET', '/books', { query: { author: '2', sort: '-price', page: '1', per_page: '5' } });
```

## Layers

* `src/http/` router and handlers (parse the request, call a service, build the response)
* `src/services/` business rules (validation, order pricing)
* `src/db/memory.js` the storage layer: `createDb()` returns the tables `books`, `authors` and `orders`.
  Rows are plain JSON-like objects; nested arrays and objects are allowed (for example a book's `tags`).
  The storage layer owns its data: what goes in and what comes out are copies, so callers can never change
  a stored row by accident.
  A table has `insert(row)`, `find(id)`, `all()`, `where(predicate)`, `update(id, patch)` and `remove(id)`.
* `src/util/` pagination, query parsing, validation, money

## Endpoints

| method and path | |
|---|---|
| `GET /books` | filters `author`, `tag`; `sort` = `title`, `price` or `-price`; `page`, `per_page` |
| `GET /books/:id`, `POST /books`, `PATCH /books/:id` | |
| `GET /authors`, `GET /authors/:id`, `POST /authors` | |
| `POST /orders`, `GET /orders/:id` | an order keeps the prices that were valid when it was placed |

Errors are `{ status, body: { error } }`: 404 unknown id, 422 invalid data.

## Tests

`npm test`
