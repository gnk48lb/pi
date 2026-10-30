import unittest

from semvr import Version, is_valid_range, max_satisfying, min_satisfying, parse_version, satisfies


class TestVersion(unittest.TestCase):
    def test_parse_and_order(self):
        self.assertEqual(str(parse_version("v1.2.3-beta.1+b5")), "1.2.3-beta.1+b5")
        self.assertLess(parse_version("1.0.0-alpha"), parse_version("1.0.0"))
        self.assertLess(parse_version("1.0.0-beta.2"), parse_version("1.0.0-beta.11"))
        self.assertEqual(parse_version("1.0.0+a"), parse_version("1.0.0+b"))
        with self.assertRaises(ValueError):
            parse_version("1.2")


class TestSatisfies(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(satisfies("1.2.3", "1.2.3"))
        self.assertTrue(satisfies("1.2.3", "=1.2.3"))
        self.assertFalse(satisfies("1.2.4", "1.2.3"))

    def test_comparators(self):
        self.assertTrue(satisfies("1.2.3", ">=1.2.0"))
        self.assertFalse(satisfies("1.2.3", ">1.2.3"))
        self.assertTrue(satisfies("1.2.3", "<=1.2.3"))
        self.assertFalse(satisfies("1.2.3", "<1.2.3"))

    def test_and_or(self):
        self.assertTrue(satisfies("1.5.0", ">=1.2.0 <2.0.0"))
        self.assertFalse(satisfies("2.0.0", ">=1.2.0 <2.0.0"))
        self.assertTrue(satisfies("3.1.0", "1.x || 3.x"))
        self.assertFalse(satisfies("2.1.0", "1.x || 3.x"))

    def test_x_ranges(self):
        self.assertTrue(satisfies("1.2.9", "1.2.x"))
        self.assertFalse(satisfies("1.3.0", "1.2.x"))
        self.assertTrue(satisfies("0.0.1", "*"))

    def test_tilde_and_caret(self):
        self.assertTrue(satisfies("1.2.9", "~1.2.3"))
        self.assertFalse(satisfies("1.3.0", "~1.2.3"))
        self.assertTrue(satisfies("1.9.0", "^1.2.3"))
        self.assertFalse(satisfies("2.0.0", "^1.2.3"))
        self.assertTrue(satisfies("0.2.9", "^0.2.3"))
        self.assertFalse(satisfies("0.3.0", "^0.2.3"))

    def test_hyphen(self):
        self.assertTrue(satisfies("2.3.4", "1.2.3 - 2.3.4"))
        self.assertFalse(satisfies("2.3.5", "1.2.3 - 2.3.4"))

    def test_prerelease_basics(self):
        self.assertTrue(satisfies("1.2.3-beta.2", ">=1.2.3-beta.1"))
        self.assertFalse(satisfies("1.2.3-beta.2", ">=1.2.0"))

    def test_invalid(self):
        with self.assertRaises(ValueError):
            satisfies("1.2.3", "1.2.3.4")
        self.assertFalse(is_valid_range(">>1"))
        self.assertTrue(is_valid_range("^1.2.3"))
        self.assertFalse(satisfies("nope", "*"))


class TestPick(unittest.TestCase):
    def test_max_min(self):
        vs = ["1.0.0", "1.2.0", "1.3.0", "2.0.0"]
        self.assertEqual(max_satisfying(vs, "^1.0.0"), "1.3.0")
        self.assertEqual(min_satisfying(vs, "^1.0.0"), "1.0.0")
        self.assertIsNone(max_satisfying(vs, ">=3"))


if __name__ == "__main__":
    unittest.main()
