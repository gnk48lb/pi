import unittest

from taskq import backoff


class BackoffTests(unittest.TestCase):
    def test_grows_and_is_capped(self):
        self.assertEqual(backoff.delay(1), 1.0)
        self.assertEqual(backoff.delay(3), 4.0)
        self.assertEqual(backoff.delay(10), 60.0)
        self.assertEqual(backoff.delay(2, base=2, factor=3, cap=100), 6)
