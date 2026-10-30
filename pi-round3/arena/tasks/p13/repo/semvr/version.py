"""Versions and their ordering, following semver.org 2.0.0.

This module is finished and tested: do not change it.  `semvr.ranges` builds on it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Tuple, Union

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    rf"^v?({_NUM})\.({_NUM})\.({_NUM})"
    rf"(?:-({_PRE_ID}(?:\.{_PRE_ID})*))?"
    rf"(?:\+({_BUILD_ID}(?:\.{_BUILD_ID})*))?$"
)


@dataclass(frozen=True, eq=False)
class Version:
    """A full version.  `prerelease` holds ints (numeric identifiers) and strs; `build` holds strs.

    Ordering follows semver precedence: major, minor and patch numerically; a version with a prerelease sorts before the
    same version without one; prerelease identifiers compare left to right (numeric identifiers are lower than
    alphanumeric ones, a shorter list is lower when all earlier identifiers are equal).  Build metadata is ignored, so
    `Version(1, 0, 0, build=("a",)) == Version(1, 0, 0, build=("b",))`.
    """

    major: int
    minor: int
    patch: int
    prerelease: Tuple[Union[int, str], ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def triple(self) -> Tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def _key(self):
        pre = tuple((0, x, "") if isinstance(x, int) else (1, 0, x) for x in self.prerelease)
        return (self.triple, 0 if self.prerelease else 1, pre)

    def __eq__(self, other):
        return isinstance(other, Version) and self._key() == other._key()

    def __hash__(self):
        return hash(self._key())

    def __lt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() < other._key()

    def __le__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() <= other._key()

    def __gt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() > other._key()

    def __ge__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() >= other._key()

    def __str__(self) -> str:
        s = "%d.%d.%d" % self.triple
        if self.prerelease:
            s += "-" + ".".join(str(x) for x in self.prerelease)
        if self.build:
            s += "+" + ".".join(self.build)
        return s

    def __repr__(self) -> str:
        return "Version(%s)" % self


def parse_version(text: str) -> Version:
    """Parse `[v]MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]`; surrounding whitespace is ignored.

    Raises ValueError for anything else (a missing part, leading zeros, empty identifiers, ...).
    """
    if not isinstance(text, str):
        raise ValueError("version must be a string, got %r" % (text,))
    m = _VERSION_RE.match(text.strip())
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    major, minor, patch, pre, build = m.groups()
    prerelease = tuple(int(x) if x.isdigit() else x for x in pre.split(".")) if pre else ()
    return Version(int(major), int(minor), int(patch), prerelease, tuple(build.split(".")) if build else ())
