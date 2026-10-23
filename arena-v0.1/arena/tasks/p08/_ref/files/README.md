# logsum

Summarise a web server access log.

## Usage

```
node bin/logsum.js [--top N] [FILE]      # FILE or standard input ("-" also means standard input)
```

Prints the number of valid and malformed lines, the total bytes, the requests per status class, the p50/p95/max latency in
milliseconds (nearest rank), the most requested paths (3 by default, `--top N` for more) and the busiest minute.

Exit codes: 0 ok, 1 file not readable, 2 usage error.

## Tests

`npm test`
