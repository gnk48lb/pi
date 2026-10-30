'use strict';

const intOr = (value, fallback) => {
  const n = parseInt(value, 10);
  return Number.isNaN(n) || n < 1 ? fallback : n;
};

function parseListQuery(query = {}) {
  return {
    author: query.author === undefined ? undefined : intOr(query.author, -1),
    tag: query.tag || undefined,
    sort: ['title', 'price', '-price'].includes(query.sort) ? query.sort : undefined,
    page: intOr(query.page, 1),
    perPage: Math.min(intOr(query.per_page, 10), 50),
  };
}

module.exports = { parseListQuery };
