'use strict';
const { notFound } = require('../http/errors');
const { validateAuthor } = require('../util/validate');

function authorService(db) {
  return {
    list() {
      return db.authors.all();
    },
    get(id) {
      const author = db.authors.find(id);
      if (!author) throw notFound('author');
      return author;
    },
    create(data) {
      validateAuthor(data);
      return db.authors.insert({ ...data });
    },
  };
}

module.exports = { authorService };
