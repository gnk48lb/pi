'use strict';
const { createApp } = require('./app');
const { createDb } = require('./db/memory');
const { seed } = require('./db/seed');

function createSeededApp() {
  const db = createDb();
  seed(db);
  return createApp(db);
}

module.exports = { createApp, createDb, createSeededApp };
