import json
import math
import os
import pathlib
import random
import subprocess
import sys
import unittest
from collections import Counter

from tests_hidden import gen

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIMIT = 25          # seconds per large case; the current implementations need hours, a sensible one needs well under one


# ---- slow oracles for small inputs (these are the ORIGINAL implementations) --------------------------------------------
def slow_dedupe(records):
    result = []
    for r in records:
        if r["id"] not in [k["id"] for k in result]:
            result.append(r)
    return result


def slow_top_tags(records, k):
    counts = {}
    for r in records:
        for t in r["tags"]:
            counts[t] = counts.get(t, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:k]


def slow_pairs(numbers, target):
    return [(i, j) for i in range(len(numbers)) for j in range(i + 1, len(numbers)) if numbers[i] + numbers[j] == target]


def slow_moving(values, window):
    return [sum(values[s:s + window]) / window for s in range(len(values) - window + 1)]


def close(a, b):
    return len(a) == len(b) and all(math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-9) for x, y in zip(a, b))


# ---- running the candidate on a big input in a child process -------------------------------------------------------------
CHILD = r"""
import json, sys
from tests_hidden import gen
import analyze
case = sys.argv[1]
if case == "dedupe":
    recs = gen.dedupe_records()
    out = analyze.dedupe(recs)
    print(json.dumps({"ids": [r["id"] for r in out]}))
elif case == "top_tags":
    print(json.dumps(analyze.top_tags(gen.tag_records(), 25)))
elif case == "pairs":
    print(json.dumps(analyze.pairs_with_sum(gen.pair_numbers(), gen.PAIRS["top"])))
elif case == "moving":
    v = gen.moving_values()
    out = analyze.moving_average(v, gen.MOVING["window"])
    print(json.dumps({"n": len(out), "sample": out[::997], "last": out[-1] if out else None}))
"""


def run_child(case):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    try:
        r = subprocess.run([sys.executable, "-c", CHILD, case], cwd=str(ROOT), env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, timeout=LIMIT)
    except subprocess.TimeoutExpired:
        raise AssertionError("%s needed more than %d s on a large input" % (case, LIMIT))
    if r.returncode != 0:
        raise AssertionError("%s crashed on a large input: %s" % (case, r.stderr[-800:]))
    return json.loads(r.stdout)


class SmallInputsKeepTheirBehaviour(unittest.TestCase):
    def test_dedupe(self):
        import analyze
        rng = random.Random(1)
        for _ in range(40):
            recs = [{"id": rng.randrange(30), "tags": [], "n": i} for i in range(rng.randrange(0, 120))]
            before = list(recs)
            got = analyze.dedupe(recs)
            want = slow_dedupe(recs)
            self.assertEqual(got, want)
            self.assertTrue(all(a is b for a, b in zip(got, want)), "records must be returned as they are, not copied")
            self.assertEqual(recs, before, "the input must not be modified")

    def test_top_tags(self):
        import analyze
        rng = random.Random(2)
        for _ in range(60):
            recs = [{"id": i, "tags": ["t%d" % rng.randrange(12) for _ in range(rng.randrange(0, 5))]} for i in range(rng.randrange(0, 60))]
            for k in (0, 1, 3, 12, 50):
                self.assertEqual(analyze.top_tags(recs, k), slow_top_tags(recs, k), (k, recs))

    def test_pairs_with_sum(self):
        import analyze
        rng = random.Random(3)
        for _ in range(60):
            nums = [rng.randrange(-5, 15) for _ in range(rng.randrange(0, 60))]
            for target in (0, 7, 10, -3):
                self.assertEqual(analyze.pairs_with_sum(nums, target), slow_pairs(nums, target), (nums, target))
        self.assertEqual(analyze.pairs_with_sum([2, 2, 2], 4), [(0, 1), (0, 2), (1, 2)])
        self.assertEqual(analyze.pairs_with_sum([5], 10), [])

    def test_moving_average(self):
        import analyze
        rng = random.Random(4)
        for _ in range(40):
            vals = [rng.uniform(-100, 100) for _ in range(rng.randrange(0, 80))]
            for w in (1, 2, 5, 79, 200):
                self.assertTrue(close(analyze.moving_average(vals, w), slow_moving(vals, w)), (w, len(vals)))
        for bad in (0, -2):
            with self.assertRaises(ValueError):
                analyze.moving_average([1, 2, 3], bad)


class LargeInputsAreFast(unittest.TestCase):
    def test_dedupe(self):
        out = run_child("dedupe")
        seen, want = set(), []
        for r in gen.dedupe_records():
            if r["id"] not in seen:
                seen.add(r["id"])
                want.append(r["id"])
        self.assertEqual(out["ids"], want)

    def test_top_tags(self):
        out = run_child("top_tags")
        counts = Counter(t for r in gen.tag_records() for t in r["tags"])
        want = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:25]
        self.assertEqual([tuple(x) for x in out], want)

    def test_pairs_with_sum(self):
        out = run_child("pairs")
        nums, target = gen.pair_numbers(), gen.PAIRS["top"]
        index = {}
        for i, x in enumerate(nums):
            index.setdefault(x, []).append(i)
        want = sorted((i, j) for j, x in enumerate(nums) for i in index.get(target - x, []) if i < j)
        self.assertEqual([tuple(x) for x in out], want)

    def test_moving_average(self):
        out = run_child("moving")
        vals, w = gen.moving_values(), gen.MOVING["window"]
        n = len(vals) - w + 1
        self.assertEqual(out["n"], n)
        for pos, got in zip(range(0, n, 997), out["sample"]):
            want = math.fsum(vals[pos:pos + w]) / w
            self.assertTrue(math.isclose(got, want, rel_tol=1e-9, abs_tol=1e-9), (pos, got, want))
        self.assertTrue(math.isclose(out["last"], math.fsum(vals[-w:]) / w, rel_tol=1e-9, abs_tol=1e-9))


if __name__ == "__main__":
    unittest.main()
