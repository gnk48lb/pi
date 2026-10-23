'use strict';
const { invalid } = require('../http/errors');

function validateBook(book, db) {
  if (!book || typeof book !== 'object') throw invalid('body must be an object');
  if (typeof book.title !== 'string' || book.title.trim() === '') throw invalid('title is required');
  if (typeof book.price !== 'number' || !(book.price >= 0)) throw invalid('price must be a number >= 0');
  if (!db.authors.find(book.authorId)) throw invalid('unknown author');
  if (book.tags !== undefined && (!Array.isArray(book.tags) || book.tags.some((t) => typeof t !== 'string'))) {
    throw invalid('tags must be an array of strings');
  }
}

function validateAuthor(author) {
  if (!author || typeof author.name !== 'string' || author.name.trim() === '') throw invalid('name is required');
}

function validateOrder(order) {
  if (!order || typeof order.customerId !== 'string') throw invalid('customerId is required');
  if (!Array.isArray(order.lines) || order.lines.length === 0) throw invalid('an order needs at least one line');
  for (const line of order.lines) {
    if (!Number.isInteger(line.qty) || line.qty < 1) throw invalid('qty must be a positive integer');
  }
}

module.exports = { validateBook, validateAuthor, validateOrder };
