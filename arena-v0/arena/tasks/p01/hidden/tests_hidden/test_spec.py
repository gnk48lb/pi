"""Hidden acceptance tests for p01: one test per README rule."""
import dataclasses
import unittest

from pager import Page, paginate


class TestSpec(unittest.TestCase):
    # ---- basics -----------------------------------------------------------
    def test_middle_page(self):
        p = paginate(list("abcdefg"), page=2, per_page=3)
        self.assertEqual(p.items, ["d", "e", "f"])
        self.assertEqual((p.page, p.per_page, p.total_items, p.total_pages), (2, 3, 7, 3))
        self.assertTrue(p.has_prev)
        self.assertTrue(p.has_next)

    def test_defaults(self):
        p = paginate(list(range(30)))
        self.assertEqual(p.items, list(range(10)))
        self.assertEqual((p.page, p.per_page, p.total_pages), (1, 10, 3))

    def test_page_is_frozen_dataclass(self):
        p = paginate([1, 2, 3])
        self.assertIsInstance(p, Page)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            p.page = 5

    # ---- rule 3: total_pages ---------------------------------------------
    def test_total_pages_exact_multiples(self):
        for n, per, expected in [(20, 10, 2), (10, 10, 1), (100, 25, 4), (21, 10, 3), (1, 10, 1), (9, 3, 3)]:
            with self.subTest(n=n, per_page=per):
                p = paginate(list(range(n)), page=1, per_page=per)
                self.assertEqual(p.total_pages, expected)

    def test_last_page_of_exact_multiple_has_no_next(self):
        p = paginate(list(range(30)), page=3, per_page=10)
        self.assertEqual(p.items, list(range(20, 30)))
        self.assertFalse(p.has_next)
        self.assertTrue(p.has_prev)

    def test_empty_input_has_one_empty_page(self):
        p = paginate([])
        self.assertEqual(p.items, [])
        self.assertEqual((p.total_items, p.total_pages), (0, 1))
        self.assertFalse(p.has_prev)
        self.assertFalse(p.has_next)

    # ---- rule 4: pages past the end --------------------------------------
    def test_page_past_the_end_is_empty(self):
        p = paginate(list(range(5)), page=9, per_page=2)
        self.assertEqual(p.items, [])
        self.assertEqual(p.page, 9)
        self.assertEqual(p.total_pages, 3)
        self.assertTrue(p.has_prev)
        self.assertFalse(p.has_next)

    def test_page_two_of_empty_input(self):
        p = paginate([], page=2)
        self.assertEqual(p.items, [])
        self.assertEqual(p.page, 2)
        self.assertTrue(p.has_prev)
        self.assertFalse(p.has_next)

    # ---- rule 1: page validation -----------------------------------------
    def test_page_below_one_raises(self):
        for bad in (0, -1, -100):
            with self.subTest(page=bad):
                with self.assertRaises(ValueError):
                    paginate([1, 2, 3], page=bad)

    def test_non_int_page_raises(self):
        for bad in (2.5, "1", None):
            with self.subTest(page=bad):
                with self.assertRaises(ValueError):
                    paginate([1, 2, 3], page=bad)

    # ---- rule 2: per_page validation -------------------------------------
    def test_per_page_range(self):
        for bad in (0, -5, 101, 1000):
            with self.subTest(per_page=bad):
                with self.assertRaises(ValueError):
                    paginate([1, 2, 3], per_page=bad)
        self.assertEqual(paginate(list(range(300)), per_page=100).items, list(range(100)))
        self.assertEqual(paginate([1, 2, 3], per_page=1).items, [1])

    def test_non_int_per_page_raises(self):
        for bad in (2.5, "10", None):
            with self.subTest(per_page=bad):
                with self.assertRaises(ValueError):
                    paginate([1, 2, 3], per_page=bad)

    # ---- "any iterable" ---------------------------------------------------
    def test_generator_input(self):
        p = paginate((i for i in range(7)), page=2, per_page=3)
        self.assertEqual(p.items, [3, 4, 5])
        self.assertEqual((p.total_items, p.total_pages), (7, 3))

    def test_tuple_range_and_string_input(self):
        self.assertEqual(paginate((1, 2, 3, 4), page=2, per_page=3).items, [4])
        self.assertEqual(paginate(range(10), page=2, per_page=4).items, [4, 5, 6, 7])
        self.assertEqual(paginate("abcde", page=3, per_page=2).items, ["e"])

    # ---- rule 5: no mutation, fresh list ---------------------------------
    def test_input_is_not_modified(self):
        data = [3, 1, 2]
        paginate(data, page=1, per_page=2)
        self.assertEqual(data, [3, 1, 2])

    def test_items_is_a_new_list(self):
        data = [1, 2, 3]
        p = paginate(data, page=1, per_page=10)
        self.assertEqual(p.items, data)
        self.assertIsNot(p.items, data)


if __name__ == "__main__":
    unittest.main()
