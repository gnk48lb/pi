import unittest

from relay import summary


class SummaryTests(unittest.TestCase):
    def test_one_region(self):
        events = [{"region": "eu", "ms": 100}, {"region": "eu", "ms": 140}]
        self.assertEqual(summary(events), "eu: 2 events, avg 120.0 ms")

    def test_no_events(self):
        self.assertEqual(summary([]), "no events")


if __name__ == "__main__":
    unittest.main()
