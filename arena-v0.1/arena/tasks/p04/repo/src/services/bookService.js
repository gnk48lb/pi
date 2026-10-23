'use strict';
const { notFound } = require('../http/errors');
const { validateBook } = require('../util/validate');

function bookService(db) {
  function get(id) {
    const book = db.books.find(id);
    if (!book) throw notFound('book');
    return book;
  }

  function search({ author, tag, sort } = {}) {
    let rows = db.books.where((b) => (author === undefined || b.authorId === author) && (!tag || b.tags.includes(tag)));
    if (sort === 'price') rows.sort((a, b) => a.price - b.price || a.id - b.id);
    else if (sort === '-price') rows.sort((a, b) => b.price - a.price || a.id - b.id);
    else if (sort === 'title') rows.sort((a, b) => a.title.localeCompare(b.title));
    return rows;
  }

  function create(data) {
    validateBook(data, db);
    return db.books.insert({ tags: [], ...data });
  }

  function update(id, patch) {
    const book = get(id);
    Object.assign(book, patch);
    validateBook(book, db);
    return book;
  }

  return { get, search, create, update };
}

module.exports = { bookService };
