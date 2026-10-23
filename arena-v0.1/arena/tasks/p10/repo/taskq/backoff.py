"""Retry delays."""


def delay(attempt, base=1.0, factor=2.0, cap=60.0):
    """Seconds to wait after the given failed attempt (1 = the first attempt)."""
    return min(cap, base * factor ** (attempt - 1))
