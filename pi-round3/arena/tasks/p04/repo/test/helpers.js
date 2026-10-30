'use strict';
const { createSeededApp } = require('../src');

const fresh = () => createSeededApp();

const ok = (res, status = 200) => {
  if (res.status !== status) throw new Error(`expected ${status}, got ${res.status}: ${JSON.stringify(res.body)}`);
  return res.body;
};

module.exports = { fresh, ok };
