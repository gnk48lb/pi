"""Hidden acceptance tests for p15.

Each check runs in fresh interpreters with PYTHONHASHSEED=0..15 and compares with the value the README prescribes, so a
test passes only if the behaviour is right for every hash seed. The expected values come from an independent oracle.
"""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEDS = list(range(16))


def run(seed, argv):
    env = dict(os.environ, PYTHONHASHSEED=str(seed))
    return subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)


class EverySeed(unittest.TestCase):
    def sweep(self, code, expected):
        bad = []
        for seed in SEEDS:
            r = run(seed, [sys.executable, "-c", "import json\nfrom relay import *\n" + code])
            if r.returncode != 0:
                bad.append("seed %d: crashed: %s" % (seed, (r.stderr.strip().splitlines() or ["?"])[-1]))
                continue
            got = json.loads(r.stdout)
            if got != expected:
                bad.append("seed %d: got %s" % (seed, json.dumps(got, ensure_ascii=False)[:300]))
        self.assertFalse(bad, "%d of %d hash seeds disagree with the README, e.g. %s" % (len(bad), len(SEEDS), bad[:2]))

    def test_visible_suite_passes_with_every_hash_seed(self):
        bad = []
        for seed in SEEDS:
            r = run(seed, [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."])
            if r.returncode != 0:
                bad.append(seed)
        self.assertEqual(bad, [], "the tests in tests/ fail with these hash seeds")

    def test_unique_keeps_first_appearance(self):
        """unique: order of first appearance, strings"""
        code = "print(json.dumps(unique(['delta', 'alpha', 'delta', 'charlie', 'alpha', 'bravo', 'echo', 'charlie'])))"
        self.sweep(code, ["delta", "alpha", "charlie", "bravo", "echo"])

    def test_unique_other_hashables_and_iterators(self):
        """unique: tuples, one-shot iterators and generators"""
        code = "print(json.dumps([unique([('b', 1), ('a', 2), ('b', 1), ('c', 3), ('a', 2)]), unique(iter('mississippi')), unique(x for x in ['z', 'y', 'z', 'x', 'y'])]))"
        self.sweep(code, [[["b", 1], ["a", 2], ["c", 3]], ["m", "i", "s", "p"], ["z", "y", "x"]])

    def test_delivery_order_smallest_ready_first(self):
        """delivery_order: ties are broken alphabetically"""
        code = "print(json.dumps(delivery_order({'d': ['b', 'c'], 'b': ['a'], 'c': ['a'], 'a': [], 'e': []})))"
        self.sweep(code, ["a", "b", "c", "d", "e"])

    def test_delivery_order_one_at_a_time_not_by_levels(self):
        """delivery_order: one channel at a time, not level by level"""
        code = "print(json.dumps([delivery_order({'a': ['b'], 'c': []}), delivery_order({'x': ['m'], 'm': [], 'k': [], 'z': ['k'], 'j': ['z']})]))"
        self.sweep(code, [["b", "a", "c"], ["k", "m", "x", "z", "j"]])

    def test_delivery_order_services_and_iterables(self):
        """delivery_order: dependencies that are only mentioned, tuples, empty input"""
        code = "print(json.dumps([delivery_order({'web': ['db', 'cache', 'queue'], 'worker': ['queue', 'db']}), delivery_order({'s': ('t', 'u'), 't': (), 'u': ('t',)}), delivery_order({})]))"
        self.sweep(code, [["cache", "db", "queue", "web", "worker"], ["t", "u", "s"], []])

    def test_delivery_order_larger_graph(self):
        """delivery_order: a 16-channel graph"""
        code = 'print(json.dumps(delivery_order({"bz": ["il", "dm", "aj"], "ha": ["ed", "im", "jx"], "ge": [], "dm": ["aj", "ga", "kh"], "ga": ["kh", "aj"], "hd": [], "il": [], "jx": ["hd", "kh", "aj"], "aj": [], "bf": [], "ed": ["kh", "bz", "il"], "hg": [], "bc": [], "im": ["bz"], "hs": ["aj", "ga"], "kh": []})))'
        self.sweep(code, ["aj", "bc", "bf", "ge", "hd", "hg", "il", "kh", "ga", "dm", "bz", "ed", "hs", "im", "jx", "ha"])

    def test_cycle_error_message_is_alphabetical(self):
        """CycleError: message lists the unschedulable channels alphabetically"""
        code = "out = []\nfor deps in [{'x': ['y'], 'y': ['z'], 'z': ['x'], 'w': []}, {'b': ['a'], 'a': ['a'], 'c': ['b']}, {'q': ['p'], 'p': ['q'], 'r': ['q'], 'm': ['r', 'p'], 'k': []}]:\n    try:\n        delivery_order(deps)\n        out.append('no error')\n    except CycleError as e:\n        out.append(str(e))\nprint(json.dumps(out))"
        self.sweep(code, ["dependency cycle among: x, y, z", "dependency cycle among: a, b, c", "dependency cycle among: m, p, q, r"])

    def test_shard_for_is_crc32(self):
        """shard_for: CRC-32 of the UTF-8 bytes modulo shards (pinned values)"""
        code = 'keys = ["alice", "bob", "carol", "dave", "eve", "frank", "grace", "heidi", "naïve-キー", ""]\nprint(json.dumps({str(n): [shard_for(k, n) for k in keys] for n in (7, 16, 1000)}))'
        self.sweep(code, {"7": [5, 2, 5, 5, 4, 3, 4, 3, 0, 0], "16": [7, 0, 3, 8, 14, 9, 3, 0, 10, 0], "1000": [735, 104, 163, 888, 790, 465, 803, 944, 482, 0]})

    def test_shard_for_bytes_keys_and_one_shard(self):
        """shard_for: bytes keys are used as they are; one shard is always 0"""
        code = 'keys = ["alice", "bob", "carol", "dave", "eve", "frank", "grace", "heidi", "naïve-キー", ""]\nprint(json.dumps([[shard_for(k.encode(\'utf-8\'), 7) for k in keys], [shard_for(k, 1) for k in keys]]))'
        self.sweep(code, [[5, 2, 5, 5, 4, 3, 4, 3, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]])

    def test_summary_first_appearance_order(self):
        """summary: regions in order of first appearance, mean with one decimal"""
        code = 'events = [{"region": "us-west", "ms": 120}, {"region": "eu", "ms": 80}, {"region": "ap", "ms": 300}, {"region": "eu", "ms": 95}, {"region": "us-west", "ms": 100}, {"region": "ap", "ms": 310}, {"region": "sa", "ms": 41.5}, {"region": "eu", "ms": 71}, {"region": "us-west", "ms": 97}, {"region": "af", "ms": 0}]\nprint(json.dumps(summary(events)))'
        self.sweep(code, "us-west: 3 events, avg 105.7 ms\neu: 3 events, avg 82.0 ms\nap: 2 events, avg 305.0 ms\nsa: 1 events, avg 41.5 ms\naf: 1 events, avg 0.0 ms")

    def test_router_recipients_alphabetical(self):
        """Router.recipients: alphabetical, also after unsubscribe"""
        code = "r = Router()\nfor who in ['mallory', 'alice', 'zed', 'bob', 'carol', 'alice', 'dave', 'erin']:\n    r.subscribe('news', who)\na = r.recipients('news')\nr.unsubscribe('news', 'bob'); r.unsubscribe('news', 'nobody')\nprint(json.dumps([a, r.recipients('news'), r.recipients('other')]))"
        self.sweep(code, [["alice", "bob", "carol", "dave", "erin", "mallory", "zed"], ["alice", "carol", "dave", "erin", "mallory", "zed"], []])

    def test_router_topics_in_first_subscription_order(self):
        """Router.topics: first-subscription order (not sorted), topics stay when emptied"""
        code = "r = Router()\nfor topic, who in [('weather', 'a'), ('alerts', 'b'), ('sports', 'c'), ('alerts', 'd'), ('news', 'e'), ('weather', 'f')]:\n    r.subscribe(topic, who)\nr.unsubscribe('sports', 'c')\nprint(json.dumps(r.topics()))"
        self.sweep(code, ["weather", "alerts", "sports", "news"])


if __name__ == "__main__":
    unittest.main()
