"""Time the four helpers on generated data.  python3 bench.py [--n N]"""
import argparse
import random
import time

import analyze


def timed(label, fn, *args):
    start = time.perf_counter()
    result = fn(*args)
    print("%-16s %8.2f s   (%d results)" % (label, time.perf_counter() - start, len(result)), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=200_000)
    n = parser.parse_args().n
    rng = random.Random(7)
    records = [{"id": rng.randrange(n // 2), "tags": ["t%d" % rng.randrange(n // 2) for _ in range(3)]} for _ in range(n)]
    numbers = [rng.randrange(0, n) for _ in range(n // 4)]
    values = [rng.random() * 100 for _ in range(n)]
    timed("dedupe", analyze.dedupe, records)
    timed("top_tags", analyze.top_tags, records, 10)
    timed("pairs_with_sum", analyze.pairs_with_sum, numbers, n)
    timed("moving_average", analyze.moving_average, values, max(2, n // 10))


if __name__ == "__main__":
    main()
