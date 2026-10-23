'use strict';

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

const notFound = (what) => new HttpError(404, `${what} not found`);
const invalid = (message) => new HttpError(422, message);

module.exports = { HttpError, notFound, invalid };
