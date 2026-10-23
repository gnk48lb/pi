"""Deterministic big inputs, shared by the test process and the child process that times the candidate."""
import random

DEDUPE = dict(n=300_000, ids=150_000)
TAGS = dict(n=200_000, vocab=100_000)
PAIRS = dict(n=60_000, top=100_000)
MOVING = dict(n=300_000, window=20_000)


def dedupe_records():
    rng = random.Random(11)
    return [{"id": rng.randrange(DEDUPE["ids"]), "tags": []} for _ in range(DEDUPE["n"])]


def tag_records():
    rng = random.Random(12)
    v = TAGS["vocab"]
    return [{"id": i, "tags": ["t%d" % int(v * rng.random() ** 2) for _ in range(3)]} for i in range(TAGS["n"])]


def pair_numbers():
    rng = random.Random(13)
    return [rng.randrange(PAIRS["top"]) for _ in range(PAIRS["n"])]


def moving_values():
    rng = random.Random(14)
    return [rng.random() * 1000 for _ in range(MOVING["n"])]
