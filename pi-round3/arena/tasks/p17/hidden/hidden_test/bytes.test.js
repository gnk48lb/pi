'use strict';
// Hidden acceptance tests for p17: the three files must be what the task asked for and, byte for byte, nothing else.
// The expected files in ./expected are the originals with exactly the requested changes applied by a byte-level script.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const want = (name) => fs.readFileSync(path.join(__dirname, 'expected', name));
const got = (rel) => fs.readFileSync(rel);

function describeDifference(a, b) {
  const n = Math.min(a.length, b.length);
  let i = 0;
  while (i < n && a[i] === b[i]) i++;
  const line = a.subarray(0, i).toString('latin1').split('\n').length;
  const hex = (buf, at) => (at < buf.length ? `0x${buf[at].toString(16).padStart(2, '0')}` : 'end of file');
  return `first difference at byte ${i} (line ${line}): got ${hex(a, i)}, expected ${hex(b, i)}; sizes ${a.length} vs ${b.length}`;
}

function sameBytes(rel, name) {
  const a = got(rel);
  const b = want(name);
  if (!a.equals(b)) assert.fail(`${rel} is not byte for byte what it should be: ${describeDifference(a, b)}`);
}

// ------------------------------------------------------------------------------------------------ src/routes.js
const ROUTE = /^\s*router\.(get|post|put|patch|delete)\((['"])(\/api\/v\d\/[^'"]*)\2/;
function routeTable(buf) {
  return buf
    .toString('latin1')
    .split(/\r?\n/)
    .map((line) => {
      const m = ROUTE.exec(line);
      return m ? `${m[1]} ${m[3]}${line.includes('// legacy: keep') ? ' (legacy)' : ''}` : null;
    })
    .filter(Boolean);
}

test('routes.js: the v1 paths became v2, except the routes marked "legacy: keep"', () => {
  const table = routeTable(got('src/routes.js'));
  assert.strictEqual(table.length, 24);
  assert.deepStrictEqual(table, routeTable(want('routes.js')));
});

test('routes.js: the line endings are unchanged (CRLF lines stay CRLF, LF lines stay LF)', () => {
  const endings = (buf) => (buf.toString('latin1').match(/\r?\n/g) || []).map((e) => e.length);
  assert.deepStrictEqual(endings(got('src/routes.js')), endings(want('routes.js')));
});

test('routes.js: the indentation is unchanged (tabs stay tabs)', () => {
  const indents = (buf) => buf.toString('latin1').split(/\r?\n/).map((l) => /^[ \t]*/.exec(l)[0]);
  assert.deepStrictEqual(indents(got('src/routes.js')), indents(want('routes.js')));
});

test('routes.js: nothing else changed, byte for byte', () => {
  sameBytes('src/routes.js', 'routes.js');
});

// ------------------------------------------------------------------------------------------------ config/manifest.json
test('manifest.json: the service version is 2.0.0 and every other value is unchanged', () => {
  assert.deepStrictEqual(JSON.parse(got('config/manifest.json').toString('utf8')), JSON.parse(want('manifest.json').toString('utf8')));
});

test('manifest.json: still the same minified file, byte for byte', () => {
  sameBytes('config/manifest.json', 'manifest.json');
});

// ------------------------------------------------------------------------------------------------ src/strings.fr
test('strings.fr: the greeting changed and the other messages are intact', () => {
  const lines = (buf) => buf.toString('latin1').split('\n');
  assert.deepStrictEqual(lines(got('src/strings.fr')), lines(want('strings.fr')));
});

test('strings.fr: still ISO-8859-1 text, byte for byte', () => {
  sameBytes('src/strings.fr', 'strings.fr');
});
