# csvstat

Print summary statistics for the numeric columns of a CSV file. No dependencies, Node 18+.

```
$ node bin/csvstat.js data/sample.csv
price: count=3 min=1.5 max=4 mean=2.6667 sum=8
qty: count=3 min=1 max=10 mean=4.3333 sum=13
```

## Usage

```
csvstat <file> [--columns name1,name2] [--format json|table|text]
```

* The first row of the file is the header.
* A column is *numeric* when every non-empty cell in it is a number and it has at
  least one non-empty cell. Empty cells are skipped, so they are not counted.
  Columns that are not numeric are ignored.
* Columns are always listed in the order they appear in the file.
* `--columns` restricts the output to the named columns (`--columns a,b` and
  `--columns=a,b` both work). A name that is not in the header is an error.
* `--format` chooses the output format (`--format json` and `--format=json` both
  work); see below. The default is `text`.
* Numbers are rounded to at most 4 decimal places; trailing zeros are dropped.

### Output formats

`text` (default), one line per column:

```
price: count=3 min=1.5 max=4 mean=2.6667 sum=8
qty: count=3 min=1 max=10 mean=4.3333 sum=13
```

`table`, cells padded to the widest value of their column:

```
column | count | min | max | mean   | sum
-------|-------|-----|-----|--------|----
price  | 3     | 1.5 | 4   | 2.6667 | 8
qty    | 3     | 1   | 10  | 4.3333 | 13
```

`json`, pretty-printed with two spaces:

```
{
  "columns": {
    "price": {
      "count": 3,
      "min": 1.5,
      "max": 4,
      "mean": 2.6667,
      "sum": 8
    },
    "qty": {
      "count": 3,
      "min": 1,
      "max": 10,
      "mean": 4.3333,
      "sum": 13
    }
  }
}
```

### Exit codes

| code | meaning                                                  |
|------|----------------------------------------------------------|
| 0    | success                                                  |
| 1    | the file could not be read                               |
| 2    | bad command line (unknown option, column or format)      |

## Development

```
npm test
```
