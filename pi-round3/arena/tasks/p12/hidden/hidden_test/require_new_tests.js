'use strict';
// The task asks for regression tests: `npm test` must run more tests than the 13 that came with the repository.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const ORIGINAL = 13;
const files = fs.readdirSync('test').filter((name) => name.endsWith('.test.js')).map((name) => path.join('test', name));
const r = spawnSync(process.execPath, ['--test', ...files], { encoding: 'utf8', timeout: 120000 });
const found = /^(?:#|ℹ)\s*tests\s+(\d+)/m.exec((r.stdout || '') + (r.stderr || ''));
const total = found ? Number(found[1]) : 0;
const added = total - ORIGINAL;
console.log(`ARENA_NOTE: regression tests added: ${added}`);
console.log(added >= 1 && r.status === 0 ? '# tests 1\n# fail 0' : '# tests 1\n# fail 1');
process.exit(added >= 1 && r.status === 0 ? 0 : 1);
