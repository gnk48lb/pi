"""Version ranges: parsing and matching (npm-style).  README.md has the rules."""
from __future__ import annotations

import re

from .version import Version, parse_version

_OPERATORS = ("<=", ">=", "<", ">", "=", "~", "^")      # longest first
_WILD = ("x", "X", "*")
_NUMBER = re.compile(r"^(?:0|[1-9][0-9]*)$")

# a primitive comparator is (operator, Version); operator is one of "=", ">", ">=", "<", "<="
_NOTHING = ("<", Version(0, 0, 0, (0,)))                 # no version is lower than 0.0.0-0


def _split_operator(token):
    for op in _OPERATORS:
        if token.startswith(op):
            return op, token[len(op):]
    return "", token


def _partial(text):
    """-> (major, minor, patch, prerelease, build); None marks a wildcard or a missing part."""
    if text in ("", *_WILD):
        return (None, None, None, (), ())
    t = text[1:] if text.startswith("v") else text
    m = re.search(r"[-+]", t)
    core, suffix = (t[:m.start()], t[m.start():]) if m else (t, "")
    parts = core.split(".")
    if len(parts) > 3:
        raise ValueError("invalid version in range: %r" % text)
    nums, wild = [], False
    for p in parts:
        if p in _WILD:
            wild = True
            nums.append(None)
        elif wild or not _NUMBER.match(p):
            raise ValueError("invalid version in range: %r" % text)
        else:
            nums.append(int(p))
    nums += [None] * (3 - len(nums))
    if suffix:
        if None in nums:
            raise ValueError("a prerelease or build needs a full version: %r" % text)
        v = parse_version(t)                              # validates the suffix
        return (nums[0], nums[1], nums[2], v.prerelease, v.build)
    return (nums[0], nums[1], nums[2], (), ())


def _lower(p):
    maj, mi, pa, pre, _ = p
    return Version(maj, mi or 0, pa or 0, pre)


def _next_minor(maj, mi):
    return Version(maj, mi + 1, 0, (0,))


def _next_major(maj):
    return Version(maj + 1, 0, 0, (0,))


def _comparison(op, p):
    maj, mi, pa, pre, build = p
    if op in ("", "="):
        if maj is None:
            return []
        if mi is None:
            return [(">=", Version(maj, 0, 0)), ("<", _next_major(maj))]
        if pa is None:
            return [(">=", Version(maj, mi, 0)), ("<", _next_minor(maj, mi))]
        return [("=", Version(maj, mi, pa, pre, build))]
    if op == ">":
        if maj is None:
            return [_NOTHING]
        if mi is None:
            return [(">=", Version(maj + 1, 0, 0))]
        if pa is None:
            return [(">=", Version(maj, mi + 1, 0))]
        return [(">", Version(maj, mi, pa, pre))]
    if op == ">=":
        return [] if maj is None else [(">=", _lower(p))]
    if op == "<":
        return [_NOTHING] if maj is None else [("<", _lower(p))]
    if op == "<=":
        if maj is None:
            return []
        if mi is None:
            return [("<", _next_major(maj))]
        if pa is None:
            return [("<", _next_minor(maj, mi))]
        return [("<=", Version(maj, mi, pa, pre))]
    if op == "~":
        if maj is None:
            return []
        return [(">=", _lower(p)), ("<", _next_major(maj) if mi is None else _next_minor(maj, mi))]
    if op == "^":
        if maj is None:
            return []
        if maj > 0:
            hi = _next_major(maj)
        elif mi is None:
            hi = _next_major(0)
        elif mi > 0:
            hi = _next_minor(0, mi)
        elif pa is None:
            hi = _next_minor(0, 0)
        else:
            hi = Version(0, 0, pa + 1, (0,))
        return [(">=", _lower(p)), ("<", hi)]
    raise ValueError("unknown operator %r" % op)


def _hyphen(lo, hi):
    out = []
    if lo[0] is not None:
        out.append((">=", _lower(lo)))
    if hi[0] is not None:
        out += _comparison("<=", hi)
    return out


def _parse_set(text):
    tokens = text.split()
    if "-" in tokens:                                      # a hyphen range is the whole set: "A - B"
        if len(tokens) != 3 or tokens[1] != "-" or _split_operator(tokens[0])[0] or _split_operator(tokens[2])[0]:
            raise ValueError("invalid hyphen range: %r" % text)
        return _hyphen(_partial(tokens[0]), _partial(tokens[2]))
    cmps, i = [], 0
    while i < len(tokens):
        op, rest = _split_operator(tokens[i])
        if op and rest == "":                              # "> 1.2.3": the version is the next token
            i += 1
            if i >= len(tokens):
                raise ValueError("operator without a version: %r" % text)
            rest = tokens[i]
        if _split_operator(rest)[0]:
            raise ValueError("two operators in a row: %r" % text)
        cmps += _comparison(op, _partial(rest))
        i += 1
    return cmps


def _parse_range(range_text):
    if not isinstance(range_text, str):
        raise ValueError("a range must be a string")
    return [_parse_set(part) for part in range_text.split("||")]


def _holds(op, bound, v):
    if op == "=":
        return v == bound
    if op == ">":
        return v > bound
    if op == ">=":
        return v >= bound
    if op == "<":
        return v < bound
    return v <= bound


def _set_matches(cmps, v):
    if not all(_holds(op, b, v) for op, b in cmps):
        return False
    if v.prerelease:                                       # a prerelease must be asked for, at its own major.minor.patch
        return any(b.prerelease and b.triple == v.triple for _, b in cmps)
    return True


def _as_version(item):
    if isinstance(item, Version):
        return item
    if isinstance(item, str):
        try:
            return parse_version(item)
        except ValueError:
            return None
    return None


def satisfies(version, range_text):
    sets = _parse_range(range_text)
    v = _as_version(version)
    return v is not None and any(_set_matches(s, v) for s in sets)


def _pick(versions, range_text, better):
    sets = _parse_range(range_text)
    best, best_v = None, None
    for item in versions:
        v = _as_version(item)
        if v is None or not any(_set_matches(s, v) for s in sets):
            continue
        if best_v is None or better(v, best_v):
            best, best_v = item, v
    return best


def max_satisfying(versions, range_text):
    return _pick(versions, range_text, lambda a, b: a > b)


def min_satisfying(versions, range_text):
    return _pick(versions, range_text, lambda a, b: a < b)


def is_valid_range(range_text):
    try:
        _parse_range(range_text)
    except ValueError:
        return False
    return True
