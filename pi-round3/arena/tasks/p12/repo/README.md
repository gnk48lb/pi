# spendsum

Summarises an expense export (CSV) into a report with one line per category, converted to US dollars.

```
node bin/spendsum.js report FILE [--month YYYY-MM] [--rates FILE]
```

## Input

A CSV file with a header row. The columns are found by name, in any order:

| column | content |
| --- | --- |
| `date` | `YYYY-MM-DD` |
| `category` | free text; rows with the same category are summed |
| `note` | free text, not used |
| `amount` | a decimal number with a dot as decimal separator. A comma may be used as thousands separator and must then separate groups of exactly three digits: `1200.50` and `1,200.50` are fine, `12,5` is not |
| `currency` | a currency code such as `EUR` |

`--month 2026-03` keeps only the rows of that month. `--rates` names a JSON file that maps each currency code to the
value of one unit in US dollars (default: `data/rates.json`).

## Output

One line per category, sorted by name, then a `TOTAL` line. Amounts are in dollars with two decimals and a comma as
thousands separator. Every row is converted and rounded to whole cents on its own before the rows are added up. With no
matching rows the report is just the `TOTAL` line (`0.00`).

```
$ node bin/spendsum.js report data/feb.csv
Food             51.80
Office           12.40
Software         99.00
Travel          101.00
TOTAL           264.20
```

## Errors

A problem in the input is reported on stderr as `spendsum: line N: <problem>`, nothing is printed on stdout and the exit
status is 2. `N` is the number of the row in the file (the header is row 1). The problems are `unknown currency "XYZ"`
(not in the rates file) and `bad amount "abc"`.

## Tests

`npm test`
