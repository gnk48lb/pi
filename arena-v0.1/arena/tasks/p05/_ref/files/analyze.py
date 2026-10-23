"""Analysis helpers for the nightly import job.  Standard library only."""
import heapq
from collections import Counter


def dedupe(records):
    """Drop records whose "id" was already seen.

    Keeps the FIRST record of every id, in the original order.  The records themselves are returned
    (not copies).
    """
    seen = set()
    result = []
    for record in records:
        rid = record["id"]
        if rid not in seen:
            seen.add(rid)
            result.append(record)
    return result


def top_tags(records, k):
    """The k most frequent tags over all records, as a list of (tag, count).

    Most frequent first; tags with the same count are ordered alphabetically.  If there are fewer
    than k distinct tags, all of them are returned.  k >= 0.
    """
    counts = Counter(tag for record in records for tag in record["tags"])
    return heapq.nsmallest(k, counts.items(), key=lambda item: (-item[1], item[0]))


def pairs_with_sum(numbers, target):
    """All index pairs (i, j) with i < j and numbers[i] + numbers[j] == target, sorted by (i, j).

    Equal numbers at different positions count as different pairs, e.g. ([2, 2, 2], 4) gives
    [(0, 1), (0, 2), (1, 2)].
    """
    positions = {}
    pairs = []
    for j, x in enumerate(numbers):
        for i in positions.get(target - x, ()):
            pairs.append((i, j))
        positions.setdefault(x, []).append(j)
    pairs.sort()
    return pairs


def moving_average(values, window):
    """Average of every full window of `window` consecutive values.

    Returns len(values) - window + 1 floats (an empty list if the window is longer than the data).
    `window` must be a positive integer, otherwise ValueError.  Floating point results are compared
    with a relative tolerance of 1e-9, so summing in a different order is fine.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if window > len(values):
        return []
    total = sum(values[:window])
    averages = [total / window]
    for i in range(window, len(values)):
        total += values[i] - values[i - window]
        averages.append(total / window)
    return averages
