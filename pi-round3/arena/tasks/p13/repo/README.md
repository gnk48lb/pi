# semvr

A small library for npm-style semantic-version **ranges**.

* `semvr/version.py` parses versions and orders them by semver 2.0.0 precedence. It is finished: do not change it.
* `semvr/ranges.py` is the part that is missing. It has to provide:

```python
satisfies(version, range)        # -> bool
max_satisfying(versions, range)  # -> the greatest satisfying element of `versions`, or None
min_satisfying(versions, range)  # -> the least satisfying element of `versions`, or None
is_valid_range(range)            # -> bool
```

`version` is a `str` or a `Version`; `range` is a `str`.

* `satisfies` returns `False` when `version` is a string that is not a valid version. It raises `ValueError` when `range`
  is not a valid range (the range is checked first, so this also happens when `version` is invalid).
* `max_satisfying` / `min_satisfying` skip elements that are not valid versions. They return the element itself, as it
  was given (a `str` stays a `str`), not a normalised copy. Elements that compare equal (they differ only in build
  metadata) are ties: the first one in the input wins. They raise `ValueError` for an invalid range, even when
  `versions` is empty.
* `is_valid_range` never raises; it returns `False` for anything that `satisfies` would reject with `ValueError`.

## Range syntax

A range is one or more **comparator sets** separated by `||`. A version satisfies the range when it satisfies at
least one of the sets. Whitespace around `||` and at both ends of the range is ignored.

A comparator set is a list of **terms** separated by whitespace (spaces, tabs, newlines). A version satisfies the set
when it satisfies every term and the pre-release rule below allows it. A set with no terms (the empty string, or the
empty side of `||`) accepts every version, again subject to the pre-release rule.

### Partial versions

A *partial* is `MAJOR[.MINOR[.PATCH]][-PRERELEASE][+BUILD]` with an optional leading `v` (`v1.2.3` is fine):

* MAJOR, MINOR and PATCH are non-negative integers without leading zeros (`0` is fine), or a wildcard: `x`, `X` or `*`.
* A part that is missing counts as a wildcard, so `1.2` is `1.2.x` and `1` is `1.x.x`. Once a part is a wildcard (or
  missing), every later part must be a wildcard (or missing) too: `1.x.3` is invalid.
* PRERELEASE and BUILD are only allowed when MAJOR, MINOR and PATCH are all numbers; `1.2-beta` and `1.x.0-beta` are
  invalid. Their syntax is the one `parse_version` accepts.
* `*`, `x`, `X` alone mean "any version".

### Terms

A term is one of

* `[OP] partial`, where `OP` is one of `=`, `>`, `>=`, `<`, `<=`, or nothing (which means `=`). Whitespace between the
  operator and the partial is allowed: `>= 1.2.3` is one term.
* `~ partial` (tilde) or `^ partial` (caret); whitespace after the `~` or `^` is allowed too.
* a **hyphen range** `partial - partial`. Whitespace is required on both sides of the hyphen (`1.2.3-2.0.0` is a single
  version with the prerelease `2.0.0`, not a range). A hyphen range must be the whole comparator set: it cannot be
  combined with other terms, and its two partials have no operator.

Anything else is invalid and raises `ValueError`: `1.2.3.4`, `1..2`, `a`, `>=` or `~` without a version, `>>1`, `=>1`,
`> =1`, `~>1`, `01.2.3`, a lone `-`, an unknown character, and so on.

### What each term means

Every term turns into primitive comparators (`=`, `>`, `>=`, `<`, `<=` against a full version). `X.Y.Z-0` below is the
smallest possible prerelease of `X.Y.Z`: using it as an *exclusive* upper bound keeps every prerelease of `X.Y.Z` out too.

| Term | Means |
|---|---|
| `1.2.3`, `=1.2.3` | exactly 1.2.3 (build metadata is ignored; a prerelease must match as well) |
| `1.2.3-beta.2` | exactly 1.2.3-beta.2 |
| `1.2`, `1.2.x`, `=1.2` | `>=1.2.0 <1.3.0-0` |
| `1`, `1.x`, `=1` | `>=1.0.0 <2.0.0-0` |
| `*`, `x`, `=*` | any version |
| `>1.2.3` | `>1.2.3` |
| `>1.2` / `>1` | `>=1.3.0` / `>=2.0.0` |
| `>*` | nothing |
| `>=1.2.3` / `>=1.2` / `>=1` / `>=*` | `>=1.2.3` / `>=1.2.0` / `>=1.0.0` / any version |
| `<1.2.3` | `<1.2.3` |
| `<1.2` / `<1` / `<*` | `<1.2.0` / `<1.0.0` / nothing |
| `<=1.2.3` | `<=1.2.3` |
| `<=1.2` / `<=1` / `<=*` | `<1.3.0-0` / `<2.0.0-0` / any version |
| `~1.2.3`, `~1.2.3-beta.2` | `>=1.2.3 <1.3.0-0`, `>=1.2.3-beta.2 <1.3.0-0` |
| `~1.2` | `>=1.2.0 <1.3.0-0` |
| `~1` | `>=1.0.0 <2.0.0-0` |
| `~0.2.3`, `~0.0.3`, `~0` | `>=0.2.3 <0.3.0-0`, `>=0.0.3 <0.1.0-0`, `>=0.0.0 <1.0.0-0` |
| `~*` | any version |
| `^1.2.3`, `^1.2.x`, `^1.x`, `^1` | `>=1.2.3 <2.0.0-0`, `>=1.2.0 <2.0.0-0`, `>=1.0.0 <2.0.0-0`, `>=1.0.0 <2.0.0-0` |
| `^0.2.3`, `^0.2.x`, `^0.2` | `>=0.2.3 <0.3.0-0`, `>=0.2.0 <0.3.0-0`, `>=0.2.0 <0.3.0-0` |
| `^0.0.3` | `>=0.0.3 <0.0.4-0` |
| `^0.0.x`, `^0.0` | `>=0.0.0 <0.1.0-0` |
| `^0.x`, `^0` | `>=0.0.0 <1.0.0-0` |
| `^1.2.3-beta.2`, `^0.0.3-beta` | `>=1.2.3-beta.2 <2.0.0-0`, `>=0.0.3-beta <0.0.4-0` |
| `^*` | any version |
| `1.2.3 - 2.3.4` | `>=1.2.3 <=2.3.4` |
| `1.2 - 2.3.4`, `1 - 2.3.4` | `>=1.2.0 <=2.3.4`, `>=1.0.0 <=2.3.4` |
| `1.2.3 - 2.3`, `1.2.3 - 2` | `>=1.2.3 <2.4.0-0`, `>=1.2.3 <3.0.0-0` |
| `1.2.3-beta.2 - 2.0.0` | `>=1.2.3-beta.2 <=2.0.0` |
| `* - 2.3.4` / `1.2.3 - *` | `<=2.3.4` / `>=1.2.3` |

The caret allows changes that do not modify the left-most non-zero part of the version (counting a missing or wildcard
part as zero); the tilde allows patch-level changes when a minor version is given and minor-level changes when it is not.

### Pre-release rule

A version that has a prerelease (`1.2.3-beta.2`) satisfies a comparator set only if **both** hold:

1. it satisfies every comparator of the set, compared by precedence, and
2. at least one comparator of that same set (after the table above, so the `X.Y.Z-0` bounds count) has a prerelease and
   the same `MAJOR.MINOR.PATCH` as the version.

So `1.2.3-beta.2` satisfies `>=1.2.3-beta.1` but not `>=1.2.0`, and `1.2.4-beta.1` does not satisfy
`>=1.2.3-beta.1 <2.0.0`. The rule is applied per set: with `||`, a prerelease may be accepted by one set and the other
sets are irrelevant. Versions without a prerelease are not affected by the rule.

(Unlike npm, which collapses a range that contains an "any" set next to other sets into plain `*`, this library does not:
each set is judged on its own.)

## Tests

`python3 -m unittest` runs the tests in `tests/`. They cover the common cases only; the rules above are the specification.
