#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const { parseCsv } = require('../src/csv');
const { numericColumns, summarize } = require('../src/stats');
const { formatText } = require('../src/format');

const USAGE = 'usage: csvstat <file> [--columns name1,name2]';

function fail(message, code = 2) {
  console.error(`Error: ${message}`);
  process.exit(code);
}

function splitList(value) {
  if (value === undefined) fail('--columns needs a value');
  return value.split(',').map((s) => s.trim()).filter((s) => s !== '');
}

function parseArgs(argv) {
  const opts = { file: null, columns: null };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '-h' || arg === '--help') {
      console.log(USAGE);
      process.exit(0);
    } else if (arg === '--columns') {
      opts.columns = splitList(argv[++i]);
    } else if (arg.startsWith('--columns=')) {
      opts.columns = splitList(arg.slice('--columns='.length));
    } else if (arg.startsWith('-')) {
      fail(`unknown option "${arg}"`);
    } else if (opts.file === null) {
      opts.file = arg;
    } else {
      fail('only one input file is supported');
    }
  }
  if (opts.file === null) fail(USAGE);
  return opts;
}

function main() {
  const opts = parseArgs(process.argv.slice(2));

  let text;
  try {
    text = fs.readFileSync(opts.file, 'utf8');
  } catch (err) {
    fail(`cannot read "${opts.file}": ${err.code || err.message}`, 1);
  }

  const table = parseCsv(text);
  if (opts.columns) {
    for (const name of opts.columns) {
      if (!table.header.includes(name)) fail(`unknown column "${name}"`);
    }
  }

  const stats = numericColumns(table, opts.columns).map((col) => ({
    name: col.name,
    ...summarize(col.values),
  }));
  process.stdout.write(formatText(stats));
}

main();
