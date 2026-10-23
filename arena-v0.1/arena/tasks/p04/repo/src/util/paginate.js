'use strict';

function paginate(items, page = 1, perPage = 10) {
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  const start = (page - 1) * perPage;
  return { items: items.slice(start, start + perPage), page, perPage, total, totalPages };
}

module.exports = { paginate };
