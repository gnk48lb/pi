from collections import Counter

from . import settings

_counts = Counter()


def count(name, n=1):
    if settings.METRICS_ENABLED:
        _counts[name] += n


def snapshot():
    return dict(_counts)


def reset():
    _counts.clear()
