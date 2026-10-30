'use strict';
const { notFound, invalid } = require('../http/errors');
const { validateOrder } = require('../util/validate');
const { sum } = require('../util/money');

function view(order) {
  const lines = order.items.map((i) => ({ bookId: i.book.id, title: i.book.title, price: i.book.price, qty: i.qty }));
  return {
    id: order.id,
    customerId: order.customerId,
    status: order.status,
    lines,
    total: sum(lines.map((l) => l.price * l.qty)),
  };
}

function orderService(db) {
  return {
    create(data) {
      validateOrder(data);
      const items = data.lines.map((line) => {
        const book = db.books.find(line.bookId);
        if (!book) throw invalid(`unknown book ${line.bookId}`);
        return { book, qty: line.qty };
      });
      return view(db.orders.insert({ customerId: data.customerId, items, status: 'new' }));
    },
    get(id) {
      const order = db.orders.find(id);
      if (!order) throw notFound('order');
      return view(order);
    },
  };
}

module.exports = { orderService };
