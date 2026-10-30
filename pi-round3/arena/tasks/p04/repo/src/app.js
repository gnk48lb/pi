'use strict';
const { createDb } = require('./db/memory');
const { createRouter } = require('./http/router');
const { bookService } = require('./services/bookService');
const { authorService } = require('./services/authorService');
const { orderService } = require('./services/orderService');
const books = require('./http/handlers/books');
const authors = require('./http/handlers/authors');
const orders = require('./http/handlers/orders');

function createApp(db = createDb()) {
  const bookSvc = bookService(db);
  const authorSvc = authorService(db);
  const orderSvc = orderService(db);
  const router = createRouter();

  router.add('GET', '/books', books.list(bookSvc));
  router.add('GET', '/books/:id', books.get(bookSvc));
  router.add('POST', '/books', books.create(bookSvc));
  router.add('PATCH', '/books/:id', books.patch(bookSvc));
  router.add('GET', '/authors', authors.list(authorSvc));
  router.add('GET', '/authors/:id', authors.get(authorSvc));
  router.add('POST', '/authors', authors.create(authorSvc));
  router.add('POST', '/orders', orders.create(orderSvc));
  router.add('GET', '/orders/:id', orders.get(orderSvc));

  return {
    db,
    services: { books: bookSvc, authors: authorSvc, orders: orderSvc },
    handle: (method, path, opts = {}) => router.dispatch(method, path, opts),
  };
}

module.exports = { createApp };
