'use strict';

const list = (authors) => () => ({ status: 200, body: authors.list() });

const get = (authors) => (req) => ({ status: 200, body: authors.get(parseInt(req.params.id, 10)) });

const create = (authors) => (req) => ({ status: 201, body: authors.create(req.body) });

module.exports = { list, get, create };
