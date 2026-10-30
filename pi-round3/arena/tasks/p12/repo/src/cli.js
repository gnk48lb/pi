'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { parseCsv } = require('./csv');
const { summarize } = require('./ledger');
const { renderReport } = require('./report');
const { SpendError } = require('./errors');

const DEFAULT_RATES = path.join(__dirname, '..', 'data', 'rates.json');
const USAGE = 'usage: spendsum report FILE [--month YYYY-MM] [--rates FILE]';

function parseArgs(argv) {
  const [command, file, ...rest] = argv;
  const opts = { command, file, month: null, rates: DEFAULT_RATES };
  for (let i = 0; i < rest.length; i += 2) {
    if (rest[i] === '--month') opts.month = rest[i + 1];
    else if (rest[i] === '--rates') opts.rates = rest[i + 1];
    else throw new SpendError(`unknown option ${rest[i]}`);
  }
  return opts;
}

// Returns the exit status.
function main(argv, out = process.stdout, err = process.stderr) {
  try {
    const opts = parseArgs(argv);
    if (opts.command !== 'report' || !opts.file) throw new SpendError(USAGE);
    const rows = parseCsv(fs.readFileSync(opts.file, 'utf8'));
    const rates = JSON.parse(fs.readFileSync(opts.rates, 'utf8'));
    out.write(renderReport(summarize(rows, rates, opts.month)));
    return 0;
  } catch (e) {
    if (e instanceof SpendError) {
      err.write(`spendsum: ${e.message}\n`);
      return 2;
    }
    throw e;
  }
}

module.exports = { main };
