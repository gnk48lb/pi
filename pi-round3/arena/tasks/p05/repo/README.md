# nightly

Helpers used by the nightly import job. Records are dicts with an `"id"` and a `"tags"` list.

* `analyze.dedupe(records)`
* `analyze.top_tags(records, k)`
* `analyze.pairs_with_sum(numbers, target)`
* `analyze.moving_average(values, window)`

The docstrings in `analyze.py` define the exact behaviour (order, tie-breaking, edge cases).

## Benchmark

```
python3 bench.py --n 200000      # the size of a real nightly run
python3 bench.py --n 2000        # quick check
```

Careful: with the current implementation the real size takes hours. Start with a small `--n`.

## Tests

```
python3 -m unittest
```
