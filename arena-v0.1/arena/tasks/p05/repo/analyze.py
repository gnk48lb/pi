"""Analysis helpers for the nightly import job.  Standard library only."""


def dedupe(records):
    """Drop records whose "id" was already seen.

    Keeps the FIRST record of every id, in the original order.  The records themselves are returned
    (not copies).
    """
    result = []
    for record in records:
        if record["id"] not in [kept["id"] for kept in result]:
            result.append(record)
    return result


def top_tags(records, k):
    """The k most frequent tags over all records, as a list of (tag, count).

    Most frequent first; tags with the same count are ordered alphabetically.  If there are fewer
    than k distinct tags, all of them are returned.  k >= 0.
    """
    counts = {}
    for record in records:
        for tag in record["tags"]:
            counts[tag] = counts.get(tag, 0) + 1
    ranked = []
    for tag, n in counts.items():
        i = 0
        while i < len(ranked) and (ranked[i][1] > n or (ranked[i][1] == n and ranked[i][0] < tag)):
            i += 1
        ranked.insert(i, (tag, n))
    return ranked[:k]


def pairs_with_sum(numbers, target):
    """All index pairs (i, j) with i < j and numbers[i] + numbers[j] == target, sorted by (i, j).

    Equal numbers at different positions count as different pairs, e.g. ([2, 2, 2], 4) gives
    [(0, 1), (0, 2), (1, 2)].
    """
    pairs = []
    for i in range(len(numbers)):
        for j in range(i + 1, len(numbers)):
            if numbers[i] + numbers[j] == target:
                pairs.append((i, j))
    return pairs


def moving_average(values, window):
    """Average of every full window of `window` consecutive values.

    Returns len(values) - window + 1 floats (an empty list if the window is longer than the data).
    `window` must be a positive integer, otherwise ValueError.  Floating point results are compared
    with a relative tolerance of 1e-9, so summing in a different order is fine.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    averages = []
    for start in range(len(values) - window + 1):
        averages.append(sum(values[start:start + window]) / window)
    return averages
