'use strict';
const register = require('./routes');
const db = require('./db');
const auth = require('./auth');

// A stub router that only records what is registered on it.
function buildApp() {
  const routes = [];
  const router = {};
  for (const method of ['get', 'post', 'put', 'patch', 'delete']) {
    router[method] = (path, ...handlers) => routes.push({ method: method.toUpperCase(), path, handlers });
  }
  register(router, { db, auth });
  return { routes, has: (method, path) => routes.some((r) => r.method === method && r.path === path) };
}

module.exports = { buildApp };
