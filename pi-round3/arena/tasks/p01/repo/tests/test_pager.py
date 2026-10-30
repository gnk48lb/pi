import unittest

from pager import paginate


class TestPaginate(unittest.TestCase):
    def test_first_page(self):
        p = paginate(list(range(25)), page=1, per_page=10)
        self.assertEqual(p.items, list(range(10)))
        self.assertEqual(p.total_pages, 3)
        self.assertTrue(p.has_next)
        self.assertFalse(p.has_prev)

    def test_last_partial_page(self):
        p = paginate(list(range(25)), page=3, per_page=10)
        self.assertEqual(p.items, [20, 21, 22, 23, 24])
        self.assertFalse(p.has_next)
        self.assertTrue(p.has_prev)

    def test_exact_multiple(self):
        p = paginate(list(range(20)), page=2, per_page=10)
        self.assertEqual(p.items, list(range(10, 20)))
        self.assertEqual(p.total_pages, 2)
        self.assertFalse(p.has_next)

    def test_zero_per_page_is_rejected(self):
        with self.assertRaises(ValueError):
            paginate([1, 2, 3], per_page=0)


if __name__ == "__main__":
    unittest.main()
