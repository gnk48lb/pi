'use strict';
const { HttpError } = require('./errors');

function compile(pattern) {
  const names = [];
  const source = pattern.replace(/:([a-z]+)/g, (_, name) => {
    names.push(name);
    return '([^/]+)';
  });
  return { regex: new RegExp(`^${source}$`), names };
}

function createRouter() {
  const routes = [];
  return {
    add(method, pattern, handler) {
      routes.push({ method, ...compile(pattern), handler });
    },
    dispatch(method, path, opts = {}) {
      for (const route of routes) {
        const match = route.method === method && route.regex.exec(path);
        if (!match) continue;
        const params = {};
        route.names.forEach((name, i) => { params[name] = decodeURIComponent(match[i + 1]); });
        try {
          return route.handler({ params, query: opts.query || {}, body: opts.body });
        } catch (err) {
          if (err instanceof HttpError) return { status: err.status, body: { error: err.message } };
          throw err;
        }
      }
      return { status: 404, body: { error: 'no such route' } };
    },
  };
}

module.exports = { createRouter };
