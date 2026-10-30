# gateway

The public API gateway of the shop. This repository holds its route table and a few configuration files.

* `src/routes.js` registers every route of the public API on a router (`router.get(path, auth(scope), handler)`, ...).
  `src/app.js` builds a stub router for the tests and registers the routes on it.
* `config/manifest.json` is the service manifest that the deployment tooling reads.
* `src/strings.fr` holds the French storefront messages; `src/i18n.js` loads them.
* `src/db.js` and `src/auth.js` are small in-memory stand-ins for the database and the auth middleware.

`npm test` runs the tests in `test/`.
