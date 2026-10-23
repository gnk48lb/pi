'use strict';
const { parseListQuery } = require('../../util/query');
const { paginate } = require('../../util/paginate');

const list = (books) => (req) => {
  const q = parseListQuery(req.query);
  const rows = books.search({ author: q.author, tag: q.tag, sort: q.sort });
  return { status: 200, body: paginate(rows, q.page, q.perPage) };
};

const get = (books) => (req) => ({ status: 200, body: books.get(parseInt(req.params.id, 10)) });

const create = (books) => (req) => ({ status: 201, body: books.create(req.body) });

const patch = (books) => (req) => ({ status: 200, body: books.update(parseInt(req.params.id, 10), req.body) });

module.exports = { list, get, create, patch };
