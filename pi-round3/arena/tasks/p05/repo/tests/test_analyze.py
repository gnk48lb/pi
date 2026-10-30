import unittest

import analyze


class DedupeTests(unittest.TestCase):
    def test_keeps_first_of_each_id_in_order(self):
        a, b, c = {"id": 1, "tags": ["x"]}, {"id": 2, "tags": []}, {"id": 1, "tags": ["y"]}
        self.assertEqual(analyze.dedupe([a, b, c]), [a, b])
        self.assertIs(analyze.dedupe([a, b, c])[0], a)

    def test_empty(self):
        self.assertEqual(analyze.dedupe([]), [])


class TopTagsTests(unittest.TestCase):
    records = [{"id": 1, "tags": ["b", "a"]}, {"id": 2, "tags": ["a", "c"]}, {"id": 3, "tags": ["c", "d", "c"]}]

    def test_most_frequent_first_ties_alphabetical(self):
        self.assertEqual(analyze.top_tags(self.records, 3), [("c", 3), ("a", 2), ("b", 1)])

    def test_k_larger_than_distinct_tags(self):
        self.assertEqual(len(analyze.top_tags(self.records, 10)), 4)

    def test_k_zero(self):
        self.assertEqual(analyze.top_tags(self.records, 0), [])


class PairsTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(analyze.pairs_with_sum([1, 2, 3, 4], 5), [(0, 3), (1, 2)])

    def test_equal_numbers(self):
        self.assertEqual(analyze.pairs_with_sum([2, 2, 2], 4), [(0, 1), (0, 2), (1, 2)])

    def test_none(self):
        self.assertEqual(analyze.pairs_with_sum([1, 2], 10), [])


class MovingAverageTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(analyze.moving_average([1, 2, 3, 4], 2), [1.5, 2.5, 3.5])

    def test_window_longer_than_data(self):
        self.assertEqual(analyze.moving_average([1, 2], 5), [])

    def test_bad_window(self):
        with self.assertRaises(ValueError):
            analyze.moving_average([1, 2, 3], 0)
