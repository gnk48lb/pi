# csvstat

Print summary statistics for the numeric columns of a CSV file. No dependencies, Node 18+.

```
$ node bin/csvstat.js data/sample.csv
price: count=3 min=1.5 max=4 mean=2.6667 sum=8
qty: count=3 min=1 max=10 mean=4.3333 sum=13
```

## Usage

```
csvstat <file> [--columns name1,name2]
```

* The first row of the file is the header.
* A column is *numeric* when every non-empty cell in it is a number and it has at
  least one non-empty cell. Empty cells are skipped, so they are not counted.
  Columns that are not numeric are ignored.
* Columns are always listed in the order they appear in the file.
* `--columns` restricts the output to the named columns (`--columns a,b` and
  `--columns=a,b` both work). A name that is not in the header is an error.
* Numbers are rounded to at most 4 decimal places; trailing zeros are dropped.

### Exit codes

| code | meaning                                        |
|------|------------------------------------------------|
| 0    | success                                        |
| 1    | the file could not be read                     |
| 2    | bad command line (unknown option or column)    |

## Development

```
npm test
```
