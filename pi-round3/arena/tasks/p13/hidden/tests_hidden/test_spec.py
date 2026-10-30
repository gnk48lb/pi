"""Hidden acceptance tests for p13: one test per case, so the report shows how much of the specification holds.

Expected values for the satisfies() cases were produced by npm's node-semver (7.6.3) and checked against the
reference solution; the invalid-range cases follow the README (npm is more lenient on a few of them).
"""
import unittest

from semvr import Version, is_valid_range, max_satisfying, min_satisfying, parse_version, satisfies

# (version, range, expected) per group
SAT = {
    'exact': [
        ('1.2.3', '1.2.3', True),
        ('1.2.3', '=1.2.3', True),
        ('1.2.3', 'v1.2.3', True),
        ('v1.2.3', '1.2.3', True),
        ('1.2.3+build.5', '1.2.3', True),
        ('1.2.3', '1.2.3+other', True),
        ('1.2.4', '1.2.3', False),
        ('1.2.3-beta', '1.2.3', False),
        ('1.2.3-beta', '1.2.3-beta', True),
        ('1.2.3-beta.1', '1.2.3-beta', False),
        ('1.2.3-2.0.0', '1.2.3-2.0.0', True),
        ('1.5.0', '1.2.3-2.0.0', False),
        ('1.2.3', '=v1.2.3', True),
        ('1.2.3-rc.1', '1.2.3-beta', False),
        ('0.0.0', '0.0.0', True),
        ('0.0.1', '0.0.0', False),
    ],
    'xrange': [
        ('1.2.9', '1.2.x', True),
        ('1.3.0', '1.2.x', False),
        ('1.2.0', '1.2', True),
        ('1.9.9', '1.x', True),
        ('2.0.0', '1.x', False),
        ('0.9.9', '*', True),
        ('5.5.5', 'x', True),
        ('5.5.5', 'X', True),
        ('1.2.3', '1.2.*', True),
        ('1.2.3', '1.*', True),
        ('2.0.0', '1', False),
        ('1.0.0', '=1', True),
        ('1.4.0', '=1.4', True),
        ('1.4.1', '=1.4', True),
        ('1.5.0', '=1.4', False),
        ('1.2.3', '', True),
        ('1.2.3', '*.*.*', True),
        ('1.2.3', '1.X', True),
        ('1.2.3', '1.2.X', True),
        ('1.1.9', '1.2.x', False),
        ('0.0.0', '0.x', True),
        ('1.0.0', '0.x', False),
        ('3.2.1', 'x.x.x', True),
    ],
    'compare': [
        ('1.2.9', '>1.2', False),
        ('1.3.0', '>1.2', True),
        ('1.9.9', '>1', False),
        ('2.0.0', '>1', True),
        ('1.2.3', '>1.2.3', False),
        ('1.2.4', '>1.2.3', True),
        ('1.2.0', '>=1.2', True),
        ('1.1.9', '>=1.2', False),
        ('1.0.0', '>=1', True),
        ('0.9.9', '>=1', False),
        ('1.1.9', '<1.2', True),
        ('1.2.0', '<1.2', False),
        ('0.9.9', '<1', True),
        ('1.0.0', '<1', False),
        ('1.2.9', '<=1.2', True),
        ('1.3.0', '<=1.2', False),
        ('1.9.9', '<=1', True),
        ('2.0.0', '<=1', False),
        ('1.2.3', '<=1.2.3', True),
        ('1.2.4', '<=1.2.3', False),
        ('9.9.9', '>*', False),
        ('0.0.0', '<*', False),
        ('1.2.3', '>=*', True),
        ('1.2.3', '<=*', True),
        ('1.2.3', '>= 1.2.3', True),
        ('1.2.2', '>= 1.2.3', False),
        ('1.9.9', '<  2', True),
        ('2.0.0', '<  2', False),
        ('1.2.4', '> 1.2.3', True),
        ('1.2.3', '> 1.2.3', False),
        ('1.2.3', '= 1.2.3', True),
        ('1.5.0', '>=1.x', True),
        ('0.5.0', '>=1.x', False),
        ('1.5.0', '>1.x', False),
        ('2.0.0', '>1.x', True),
        ('1.5.0', '<=1.x', True),
        ('2.0.0', '<=1.x', False),
        ('0.9.9', '<1.x', True),
        ('1.0.0', '<1.x', False),
    ],
    'tilde': [
        ('1.2.2', '~1.2.3', False),
        ('1.2.3', '~1.2.3', True),
        ('1.2.99', '~1.2.3', True),
        ('1.3.0', '~1.2.3', False),
        ('1.2.0', '~1.2', True),
        ('1.2.9', '~1.2', True),
        ('1.3.0', '~1.2', False),
        ('1.1.9', '~1.2', False),
        ('1.0.0', '~1', True),
        ('1.9.9', '~1', True),
        ('2.0.0', '~1', False),
        ('0.9.9', '~1', False),
        ('0.2.3', '~0.2.3', True),
        ('0.2.9', '~0.2.3', True),
        ('0.3.0', '~0.2.3', False),
        ('0.0.3', '~0.0.3', True),
        ('0.0.9', '~0.0.3', True),
        ('0.1.0', '~0.0.3', False),
        ('0.0.0', '~0', True),
        ('0.9.9', '~0', True),
        ('1.0.0', '~0', False),
        ('1.2.3', '~ 1.2.3', True),
        ('1.2.5', '~1.2.x', True),
        ('1.3.0', '~1.2.x', False),
        ('5.0.0', '~*', True),
        ('1.2.3', '~v1.2.3', True),
        ('1.9.0', '~1.x', True),
        ('2.0.0', '~1.x', False),
    ],
    'caret': [
        ('1.2.2', '^1.2.3', False),
        ('1.2.3', '^1.2.3', True),
        ('1.9.9', '^1.2.3', True),
        ('2.0.0', '^1.2.3', False),
        ('0.2.3', '^0.2.3', True),
        ('0.2.9', '^0.2.3', True),
        ('0.3.0', '^0.2.3', False),
        ('0.2.2', '^0.2.3', False),
        ('0.0.3', '^0.0.3', True),
        ('0.0.4', '^0.0.3', False),
        ('0.0.2', '^0.0.3', False),
        ('1.2.0', '^1.2.x', True),
        ('1.9.0', '^1.2.x', True),
        ('2.0.0', '^1.2.x', False),
        ('1.1.9', '^1.2.x', False),
        ('1.0.0', '^1.x', True),
        ('1.99.0', '^1.x', True),
        ('2.0.0', '^1.x', False),
        ('0.0.0', '^0.0.x', True),
        ('0.0.9', '^0.0.x', True),
        ('0.1.0', '^0.0.x', False),
        ('0.0.5', '^0.0', True),
        ('0.1.0', '^0.0', False),
        ('0.0.0', '^0.x', True),
        ('0.9.9', '^0.x', True),
        ('1.0.0', '^0.x', False),
        ('0.5.0', '^0', True),
        ('1.0.0', '^0', False),
        ('0.2.0', '^0.2', True),
        ('0.2.9', '^0.2', True),
        ('0.3.0', '^0.2', False),
        ('0.2.5', '^0.2.x', True),
        ('0.3.0', '^0.2.x', False),
        ('1.0.0', '^1', True),
        ('2.0.0', '^1', False),
        ('1.2.3', '^ 1.2.3', True),
        ('1.2.2', '^ 1.2.3', False),
        ('8.8.8', '^*', True),
        ('0.0.0', '^0.0.0', True),
        ('0.0.1', '^0.0.0', False),
        ('1.4.0', '^v1.2.3', True),
        ('3.0.0', '^1.2.3 || ^3.0.0', True),
    ],
    'hyphen': [
        ('1.2.2', '1.2.3 - 2.3.4', False),
        ('1.2.3', '1.2.3 - 2.3.4', True),
        ('2.3.4', '1.2.3 - 2.3.4', True),
        ('2.3.5', '1.2.3 - 2.3.4', False),
        ('1.2.0', '1.2 - 2.3.4', True),
        ('1.1.9', '1.2 - 2.3.4', False),
        ('1.0.0', '1 - 2.3.4', True),
        ('0.9.9', '1 - 2.3.4', False),
        ('2.3.9', '1.2.3 - 2.3', True),
        ('2.4.0', '1.2.3 - 2.3', False),
        ('2.9.9', '1.2.3 - 2', True),
        ('3.0.0', '1.2.3 - 2', False),
        ('0.0.1', '* - 2.3.4', True),
        ('2.3.5', '* - 2.3.4', False),
        ('99.0.0', '1.2.3 - *', True),
        ('1.2.2', '1.2.3 - *', False),
        ('2.0.0', '1.2.3\t-\t2.3.4', True),
        ('1.2.3-beta.2', '1.2.3-beta.2 - 2.0.0', True),
        ('1.2.3-beta.1', '1.2.3-beta.2 - 2.0.0', False),
        ('1.2.3', '1.2.3-beta.2 - 2.0.0', True),
        ('1.5.0', 'v1.2.3 - v2.0.0', True),
        ('2.0.1', 'v1.2.3 - v2.0.0', False),
        ('1.2.3-beta', '1.2.3-beta - 1.2.3', True),
        ('1.5.0', '  1.2.3   -   2.3.4  ', True),
        ('3.0.0', '1.2.3 - 2.0.0 || 3.x', True),
        ('2.5.0', '1.2.3 - 2.0.0 || 3.x', False),
    ],
    'or': [
        ('1.2.5', '1.2.x || 2.x', True),
        ('2.5.0', '1.2.x || 2.x', True),
        ('1.3.0', '1.2.x || 2.x', False),
        ('3.0.0', '1.2.x || 2.x', False),
        ('0.5.0', '<1.0.0 || >=2.0.0', True),
        ('1.5.0', '<1.0.0 || >=2.0.0', False),
        ('2.0.0', '<1.0.0 || >=2.0.0', True),
        ('2.5.0', '^1.2.3 || ^2.0.0', True),
        ('1.2.3', '1.2.3 || 1.2.4', True),
        ('1.2.4', '1.2.3 || 1.2.4', True),
        ('1.2.5', '1.2.3 || 1.2.4', False),
        ('1.2.4', '  1.2.3  ||  1.2.4  ', True),
        ('5.0.0', '^1.0.0 || ', True),
        ('0.0.1', '|| 1.2.3', True),
        ('0.0.1', '||', True),
        ('9.9.9', '1.2.3 ||', True),
        ('1.0.0', '1.x || 2.x || 3.x', True),
        ('3.1.0', '1.x || 2.x || 3.x', True),
        ('4.0.0', '1.x || 2.x || 3.x', False),
        ('1.5.0', '>=1.2.3 <1.4.0 || >=1.5.0 <1.6.0', True),
        ('1.4.5', '>=1.2.3 <1.4.0 || >=1.5.0 <1.6.0', False),
    ],
    'and': [
        ('1.5.0', '>=1.2.3 <2.0.0', True),
        ('2.0.0', '>=1.2.3 <2.0.0', False),
        ('1.2.2', '>=1.2.3 <2.0.0', False),
        ('1.2.3', '>1.2.3 <=1.2.5', False),
        ('1.2.4', '>1.2.3 <=1.2.5', True),
        ('1.2.5', '>1.2.3 <=1.2.5', True),
        ('1.2.6', '>1.2.3 <=1.2.5', False),
        ('1.4.0', '^1.2.3 <1.5.0', True),
        ('1.5.0', '^1.2.3 <1.5.0', False),
        ('1.2.4', '~1.2 >=1.2.5', False),
        ('1.2.5', '~1.2 >=1.2.5', True),
        ('1.2.9', '>1.2 <1.4', False),
        ('1.3.0', '>1.2 <1.4', True),
        ('1.3.9', '>1.2 <1.4', True),
        ('1.4.0', '>1.2 <1.4', False),
        ('1.4.9', '1.x >=1.5.0', False),
        ('1.5.0', '1.x >=1.5.0', True),
        ('1.5.0', '>= 1.2.3 < 2', True),
        ('2.0.0', '>= 1.2.3 < 2', False),
        ('1.5.0', '\t>=1.2.3\n<2.0.0\t', True),
        ('1.5.0', '>=1.2.3\t<2.0.0', True),
        ('1.0.0', '>=1.0.0 <1.0.0', False),
        ('1.5.0', '  >=1.2.3    <2.0.0  ', True),
        ('1.2.3', '>=1.2.3 <=1.2.3', True),
        ('1.2.3', '1.2.3 1.2.3', True),
        ('1.2.3', '1.2.3 1.2.4', False),
    ],
    'prerelease': [
        ('1.2.3-beta.2', '>=1.2.3-beta.1', True),
        ('1.2.3-beta.2', '>=1.2.0', False),
        ('1.2.4-beta.1', '>=1.2.3-beta.1 <2.0.0', False),
        ('1.2.3-beta.2', '>=1.2.3-beta.1 <2.0.0', True),
        ('1.2.3-beta.2', '^1.2.0', False),
        ('1.2.3-beta.2', '^1.2.3-beta.1', True),
        ('1.2.3-beta.2', '^1.2.3-beta.3', False),
        ('1.3.0-beta', '^1.2.3-beta.1', False),
        ('1.2.3-beta.2', '~1.2.3-beta.1', True),
        ('2.0.0-beta', '^1.2.3', False),
        ('2.0.0-0', '^1.2.3', False),
        ('1.2.3-0', '^1.2.3', False),
        ('2.0.0-alpha', '>=1.0.0 <2.0.0', False),
        ('2.0.0-alpha', '<2.0.0-beta', True),
        ('1.0.0-rc.1', '>=1.0.0-rc.0 <1.0.0', True),
        ('1.0.0-rc.1', '<1.0.0', False),
        ('1.2.3-beta.2', '*', False),
        ('1.2.3-beta.2', 'x', False),
        ('1.2.3-beta.2', '', False),
        ('1.2.3-beta.2', '>=0.0.0', False),
        ('1.2.3-beta.2', '1.2.x', False),
        ('1.2.3-beta.2', '1.x', False),
        ('0.0.3-beta', '^0.0.3-alpha', True),
        ('0.0.4-alpha', '^0.0.3-alpha', False),
        ('1.2.3-beta.2', '>=1.2.3-beta.1 || 3.x', True),
        ('3.1.0-beta', '>=1.2.3-beta.1 || 3.x', False),
        ('1.2.3-beta.2', '3.x || >=1.2.3-beta.1', True),
        ('1.2.3-beta.10', '>1.2.3-beta.2', True),
        ('1.2.3-beta.11', '<1.2.3-beta.2', False),
        ('1.2.3-alpha', '>=1.2.3-1', True),
        ('1.2.3-1', '>=1.2.3-alpha', False),
        ('1.2.3', '>=1.2.3-beta', True),
        ('1.2.3', '^1.2.3-beta.2', True),
        ('1.2.3-beta.2', '<=1.2.3-beta.2', True),
        ('1.2.3-beta.3', '<=1.2.3-beta.2', False),
        ('1.2.3-alpha.1', '<1.2.3-alpha.beta >1.2.3-alpha', True),
        ('1.2.3-alpha.beta', '<1.2.3-alpha.beta >1.2.3-alpha', False),
        ('2.0.0-rc.1', '1.5.0 - 2.0.0', False),
        ('2.0.0-rc.1', '1.5.0 - 2.0.0-rc.2', True),
        ('1.2.3-beta', '<=1.2.3', False),
        ('1.2.3-beta', '<1.2.3-rc <=1.2.3', True),
        ('1.2.3-beta+build.7', '>=1.2.3-beta', True),
    ],
    'build': [
        ('1.2.3+b', '>=1.2.3', True),
        ('1.2.3+b', '1.2.3+c', True),
        ('1.2.3', '>1.2.3+zzz', False),
        ('1.2.3+zzz', '>1.2.3', False),
        ('1.2.3+a', '<1.2.3+b', False),
        ('1.2.3-beta+x', '>=1.2.3-beta', True),
    ],
    'invalid_version': [
        ('', '*', False),
        ('not-a-version', '*', False),
        ('1.2', '*', False),
        ('1.2.3.4', '*', False),
        ('01.2.3', '*', False),
        ('1.2.3-', '*', False),
        ('v', '*', False),
        ('1.x', '*', False),
    ],
}

INVALID = [
    '1.2.3.4',
    '1.x.3',
    'a.b.c',
    '1.2.a',
    'x.1.2',
    '*.1',
    '1.*.3',
    '>=',
    '~',
    '^',
    '>',
    '<=',
    '=',
    '>>1.2.3',
    '=>1.2.3',
    '=<1.2.3',
    '> =1.2.3',
    '~>1.2.3',
    '~~1',
    '^^1',
    '01.2.3',
    '1.02.3',
    '1.2.03',
    '1.2.3 -',
    '- 1.2.3',
    '-',
    '1.2.3 - 2.0.0 3.0.0',
    '1.2.3 - 2.0.0 <3.0.0',
    '<3.0.0 1.2.3 - 2.0.0',
    '>=1.2.3 - 2.0.0',
    '1.2.3 - >=2.0.0',
    '<1.2.3 - 2.0.0',
    '1.2.3 -2.0.0',
    '1.2.3- 2.0.0 -',
    '1.2.3 - 2.0.0 - 3.0.0',
    '1.2-beta',
    '1.x.0-beta',
    '1.2.3-',
    '1.2.3+',
    '1..2',
    'v',
    'vv1.2.3',
    '1.2.3 || 1.2.3.4',
    '1.2.3 || a',
    '1.2.3 || >',
    '1.2.3 | 2',
    '1.2.3 ||| 2',
    '$1.2.3',
    '1.2.3-beta..1',
    '1.2.3-01',
    '1.2.3-beta!',
    '1.2.3+build!',
    '1.2.3 @ 2',
    '^1.2.3 - 2',
    '1.2.x-beta',
    '1.2.3.',
    '1.2.3-beta+',
    '=',
    '> > 1.2.3',
    '1.2.3 >= ',
    '<>1.2.3',
]

VALID = [
    '',
    '*',
    'x',
    'X',
    '*.*.*',
    '1.2.3',
    'v1.2.3',
    '=v1.2.3',
    '>= 1.2.3',
    '^ 1.2',
    '~ 1',
    '~1',
    '1.2.3 - 2',
    '1.2.3-2.0.0',
    '||',
    '1 || 2',
    '1.2.3 ||',
    ' 1.2.3 ',
    '1.x.x',
    'x.x.x',
    '1.2.3-beta.1+build.5',
    '>=1.2.3-beta <2',
    '^0.0.0',
    '<*',
    '>*',
    '1.2.3 \t 4.5.6',
    '1.2.3 - 2.3.4',
    '\t1.2.3\n',
    '^1.2.3 || ~2.1 || >=3 <4',
    '1.2.3-beta-1',
    '1.2.3-a.b.c.d',
    '1.2.3+a-b.c',
]


class TestSpec(unittest.TestCase):
    """The generated cases are attached below as test_<group>_<n>; the hand-written ones follow."""

    # ---- API behaviour --------------------------------------------------------------------------------------------
    def test_api_invalid_range_checked_before_version(self):
        with self.assertRaises(ValueError):
            satisfies("not a version", "1.2.3.4")

    def test_api_version_objects(self):
        self.assertTrue(satisfies(Version(1, 2, 3), "^1.0.0"))
        self.assertFalse(satisfies(Version(2, 0, 0), "^1.0.0"))
        self.assertTrue(satisfies(parse_version("1.2.3-beta.2"), ">=1.2.3-beta.1"))
        self.assertFalse(satisfies(parse_version("1.2.3-beta.2"), ">=1.2.0"))

    def test_api_returns_bool(self):
        self.assertIs(satisfies("1.2.3", "^1.0.0"), True)
        self.assertIs(satisfies("2.0.0", "^1.0.0"), False)
        self.assertIs(satisfies("nope", "*"), False)
        self.assertIs(is_valid_range("^1"), True)
        self.assertIs(is_valid_range("^^1"), False)

    def test_api_is_valid_range_never_raises(self):
        for r in ("", "1.2.3.4", ">=", "||", "1.2.3 - ", "\x00", "1.2.3\x00", "é", "1.2.3 ¶ 2"):
            self.assertIn(is_valid_range(r), (True, False))
        self.assertFalse(is_valid_range("é"))
        self.assertFalse(is_valid_range("1.2.3\x00"))

    def test_api_range_must_be_checked_even_without_candidates(self):
        with self.assertRaises(ValueError):
            max_satisfying([], "1.x.3")
        with self.assertRaises(ValueError):
            min_satisfying([], ">=")
        self.assertIsNone(max_satisfying([], "^1.0.0"))
        self.assertIsNone(min_satisfying([], "^1.0.0"))

    # ---- max_satisfying / min_satisfying -----------------------------------------------------------------------
    def test_pick_basic(self):
        vs = ["1.0.0", "1.2.0", "1.2.5", "1.3.0", "2.0.0"]
        self.assertEqual(max_satisfying(vs, "^1.0.0"), "1.3.0")
        self.assertEqual(min_satisfying(vs, "^1.0.0"), "1.0.0")
        self.assertEqual(max_satisfying(vs, "~1.2.0"), "1.2.5")
        self.assertEqual(min_satisfying(vs, "~1.2.0"), "1.2.0")
        self.assertIsNone(max_satisfying(vs, ">=3"))
        self.assertIsNone(min_satisfying(vs, ">=3"))
        self.assertEqual(min_satisfying(vs, "<1.2"), "1.0.0")
        self.assertEqual(max_satisfying(vs, "<1.2"), "1.0.0")
        self.assertEqual(max_satisfying(vs, "*"), "2.0.0")

    def test_pick_unsorted_and_duplicates(self):
        vs = ["1.10.0", "1.2.0", "1.9.0", "1.2.0", "1.10.0"]
        self.assertEqual(max_satisfying(vs, "1.x"), "1.10.0")
        self.assertEqual(min_satisfying(vs, "1.x"), "1.2.0")

    def test_pick_skips_invalid_versions(self):
        vs = ["x", "1.0.0", "1.0", "1.5.0", "v1.2.0", "", "1.2.3.4"]
        self.assertEqual(max_satisfying(vs, "^1.0.0"), "1.5.0")
        self.assertEqual(max_satisfying(vs, "<1.5.0"), "v1.2.0")
        self.assertEqual(min_satisfying(vs, ">1.0.0"), "v1.2.0")

    def test_pick_returns_the_element_itself(self):
        a, b = Version(1, 0, 0), Version(1, 1, 0)
        self.assertIs(max_satisfying([a, b], "^1.0.0"), b)
        self.assertIs(min_satisfying([a, b], "^1.0.0"), a)
        mixed = ["1.0.0", b]
        self.assertIs(max_satisfying(mixed, "^1.0.0"), b)
        self.assertEqual(min_satisfying(mixed, "^1.0.0"), "1.0.0")

    def test_pick_ties_first_wins(self):
        self.assertEqual(max_satisfying(["1.2.3+a", "1.2.3+b"], "1.x"), "1.2.3+a")
        self.assertEqual(min_satisfying(["1.2.3+a", "1.2.3+b"], "1.x"), "1.2.3+a")
        self.assertEqual(max_satisfying(["1.2.3+b", "1.2.3+a"], "1.x"), "1.2.3+b")
        self.assertEqual(max_satisfying(["1.0.0", "1.2.3+z", "1.2.3"], "1.x"), "1.2.3+z")

    def test_pick_prereleases_follow_the_rule(self):
        vs = ["1.2.3", "1.3.0-beta", "1.3.0-rc.1"]
        self.assertEqual(max_satisfying(vs, "^1.2.0"), "1.2.3")
        self.assertEqual(max_satisfying(vs, "1.x"), "1.2.3")
        self.assertEqual(max_satisfying(vs, ">=1.3.0-alpha"), "1.3.0-rc.1")
        self.assertEqual(min_satisfying(vs, ">=1.3.0-alpha"), "1.3.0-beta")
        self.assertEqual(max_satisfying(["1.3.0-beta"], "^1.2.0"), None)

    def test_pick_prerelease_precedence(self):
        vs = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0"]
        self.assertEqual(max_satisfying(vs, ">=1.0.0-alpha"), "1.0.0")
        self.assertEqual(min_satisfying(vs, ">=1.0.0-alpha"), "1.0.0-alpha")
        self.assertEqual(max_satisfying(vs, ">=1.0.0-alpha <1.0.0"), "1.0.0-rc.1")
        self.assertEqual(max_satisfying(vs, ">=1.0.0-alpha <1.0.0-beta.2"), "1.0.0-beta")
        self.assertEqual(min_satisfying(vs, ">1.0.0-alpha.1"), "1.0.0-alpha.beta")
        self.assertEqual(max_satisfying(vs, "<1.0.0-beta.11 >1.0.0-beta"), "1.0.0-beta.2")

    def test_pick_accepts_any_iterable_once(self):
        self.assertEqual(max_satisfying((v for v in ["1.0.0", "1.4.0", "1.1.0"]), "^1.0.0"), "1.4.0")
        self.assertEqual(min_satisfying(iter(["1.4.0", "1.1.0"]), "^1.0.0"), "1.1.0")
        self.assertEqual(max_satisfying(("1.0.0", "1.4.0"), "^1.0.0"), "1.4.0")

    def test_pick_with_or_ranges(self):
        vs = ["0.5.0", "1.5.0", "2.5.0", "3.5.0"]
        self.assertEqual(max_satisfying(vs, "<1.0.0 || >=2.0.0 <3.0.0"), "2.5.0")
        self.assertEqual(min_satisfying(vs, "<1.0.0 || >=2.0.0 <3.0.0"), "0.5.0")
        self.assertEqual(max_satisfying(vs, "1.x || 3.x"), "3.5.0")

    def test_pick_whole_range_is_validated_not_just_the_matching_set(self):
        with self.assertRaises(ValueError):
            max_satisfying(["1.2.3"], "1.2.3 || 1.2.3.4")


def _add(name, fn):
    fn.__name__ = name
    setattr(TestSpec, name, fn)


def _sat_case(v, r, expected):
    def test(self):
        self.assertIs(satisfies(v, r), expected, "satisfies(%r, %r) should be %r" % (v, r, expected))
    return test


def _invalid_case(r):
    def test(self):
        with self.assertRaises(ValueError, msg="satisfies('1.2.3', %r) should raise ValueError" % (r,)):
            satisfies("1.2.3", r)
        self.assertFalse(is_valid_range(r), "is_valid_range(%r) should be False" % (r,))
    return test


def _valid_case(r):
    def test(self):
        self.assertTrue(is_valid_range(r), "is_valid_range(%r) should be True" % (r,))
        self.assertIn(satisfies("1.2.3", r), (True, False))
    return test


for _group, _rows in SAT.items():
    for _i, (_v, _r, _e) in enumerate(_rows):
        _add("test_%s_%03d" % (_group, _i), _sat_case(_v, _r, _e))
for _i, _r in enumerate(INVALID):
    _add("test_invalid_%03d" % _i, _invalid_case(_r))
for _i, _r in enumerate(VALID):
    _add("test_valid_%03d" % _i, _valid_case(_r))


if __name__ == "__main__":
    unittest.main()
