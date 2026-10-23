'use strict';

const AUTHORS = [
  { id: 1, name: 'Ursula Vance', born: 1931 },
  { id: 2, name: 'Tomas Reyes', born: 1958 },
  { id: 3, name: 'Hana Ito', born: 1972 },
  { id: 4, name: 'Dmitri Volkov', born: 1946 },
];

const BOOKS = [
  ['The Salt Road', 1, 12.5, ['travel', 'history']],
  ['Lanterns', 1, 9.99, ['poetry']],
  ['Glass Orchard', 1, 14.0, ['fiction']],
  ['Night Ferry', 2, 11.25, ['fiction', 'mystery']],
  ['Tidewater', 2, 18.0, ['history']],
  ['Small Engines', 2, 24.5, ['technical']],
  ['Paper Moons', 3, 8.75, ['fiction']],
  ['Hollow Hours', 3, 10.0, ['fiction', 'mystery']],
  ['The Quiet Atlas', 3, 21.0, ['travel']],
  ['Iron Weather', 4, 16.4, ['history', 'technical']],
  ['Winter Ledger', 4, 13.3, ['fiction']],
  ['Cold Arithmetic', 4, 19.9, ['technical']],
];

function seed(db) {
  for (const author of AUTHORS) db.authors.insert(Object.assign({}, author));
  for (const [title, authorId, price, tags] of BOOKS) {
    db.books.insert({ title, authorId, price, tags: tags.slice(), dimensions: { w: 14, h: 21 } });
  }
}

module.exports = { seed, AUTHORS, BOOKS };
