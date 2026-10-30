"""Version ranges: parsing and matching.  This is the module to write; README.md has the rules."""
from __future__ import annotations

from .version import Version, parse_version  # noqa: F401  (you will need them)


def satisfies(version, range_text):
    raise NotImplementedError


def max_satisfying(versions, range_text):
    raise NotImplementedError


def min_satisfying(versions, range_text):
    raise NotImplementedError


def is_valid_range(range_text):
    raise NotImplementedError
