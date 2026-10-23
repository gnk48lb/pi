'use strict';

const create = (orders) => (req) => ({ status: 201, body: orders.create(req.body) });

const get = (orders) => (req) => ({ status: 200, body: orders.get(parseInt(req.params.id, 10)) });

module.exports = { create, get };
