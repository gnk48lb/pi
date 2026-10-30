import unittest

from relay import unique


class UniqueTests(unittest.TestCase):
    def test_keeps_the_first_appearance_of_each_item(self):
        self.assertEqual(unique(["b", "a", "b"]), ["b", "a"])

    def test_numbers(self):
        self.assertEqual(unique([1, 2, 2, 1]), [1, 2])

    def test_empty(self):
        self.assertEqual(unique([]), [])


if __name__ == "__main__":
    unittest.main()
