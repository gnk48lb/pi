#!/usr/bin/env node
'use strict';
const fs = require('node:fs');

const LINE = /^(\S+) \S+ \S+ \[(\d{2}\/[A-Za-z]{3}\/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4})\] "(\S+) (\S+) (\S+)" (\d{3}) (\d+|-) (\d+(?:\.\d+)?)$/;

function usage(message) {
  if (message) process.stderr.write(`logsum: ${message}\n`);
  process.stderr.write('usage: logsum [--top N] [FILE]\n');
  process.exit(2);
}

function parseArgs(argv) {
  const opts = { top: 3, file: null };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--top' || arg.startsWith('--top=')) {
      const value = arg === '--top' ? argv[++i] : arg.slice(6);
      if (!/^[1-9][0-9]*$/.test(value || '')) usage(`--top needs a positive integer, got ${JSON.stringify(value)}`);
      opts.top = Number(value);
    } else if (arg === '-') {
      if (opts.file !== null) usage('too many arguments');
      opts.file = '-';
    } else if (arg.startsWith('-')) {
      usage(`unknown option ${arg}`);
    } else {
      if (opts.file !== null) usage('too many arguments');
      opts.file = arg;
    }
  }
  return opts;
}

function summarise(text, top) {
  let valid = 0;
  let malformed = 0;
  let bytes = 0;
  const classes = { 2: 0, 3: 0, 4: 0, 5: 0 };
  const latencies = [];
  const paths = new Map();
  const minutes = new Map();
  for (const raw of text.split('\n')) {
    const line = raw.endsWith('\r') ? raw.slice(0, -1) : raw;
    if (line.trim() === '') continue;
    const m = LINE.exec(line);
    if (!m) {
      malformed++;
      continue;
    }
    valid++;
    bytes += m[7] === '-' ? 0 : Number(m[7]);
    const cls = Number(m[6][0]);
    if (cls in classes) classes[cls]++;
    latencies.push(Math.round(Number(m[8]) * 1000));
    const path = m[4].split('?')[0];
    paths.set(path, (paths.get(path) || 0) + 1);
    const minute = m[2].slice(0, 17);
    minutes.set(minute, (minutes.get(minute) || 0) + 1);
  }
  const out = [`requests: ${valid} (valid), ${malformed} (malformed)`];
  if (valid === 0) {
    out.push('no valid requests');
    return out.join('\n') + '\n';
  }
  latencies.sort((a, b) => a - b);
  const rank = (p) => latencies[Math.ceil((p / 100) * latencies.length) - 1];
  out.push(`bytes: ${bytes}`);
  out.push(`status: 2xx=${classes[2]} 3xx=${classes[3]} 4xx=${classes[4]} 5xx=${classes[5]}`);
  out.push(`latency ms: p50=${rank(50)} p95=${rank(95)} max=${latencies[latencies.length - 1]}`);
  out.push('top paths:');
  const ranked = [...paths.entries()].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  for (const [path, n] of ranked.slice(0, top)) out.push(`  ${path} ${n}`);
  let best = null;
  for (const [minute, n] of minutes) if (best === null || n > best[1]) best = [minute, n];
  out.push(`busiest minute: ${best[0]} (${best[1]} requests)`);
  return out.join('\n') + '\n';
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  let text;
  try {
    text = opts.file === null || opts.file === '-' ? fs.readFileSync(0, 'utf8') : fs.readFileSync(opts.file, 'utf8');
  } catch (err) {
    process.stderr.write(`logsum: cannot read ${opts.file}\n`);
    process.exit(1);
  }
  process.stdout.write(summarise(text, opts.top));
}

main();
