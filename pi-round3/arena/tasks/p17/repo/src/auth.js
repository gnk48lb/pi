'use strict';

// Stand-in for the real auth middleware: `auth(scope)` returns a middleware that lets everything through.
module.exports = function auth(scope) {
  return function authorize(req, res, next) {
    if (next) next();
  };
};
