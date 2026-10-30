import unittest

from relay import CycleError, delivery_order


class DeliveryOrderTests(unittest.TestCase):
    def test_a_chain_is_delivered_in_dependency_order(self):
        self.assertEqual(delivery_order({"push": ["sms"], "sms": ["email"]}), ["email", "sms", "push"])

    def test_a_channel_that_is_only_a_dependency_is_still_delivered(self):
        self.assertEqual(delivery_order({"a": ["b"]}), ["b", "a"])

    def test_a_cycle_is_an_error(self):
        with self.assertRaises(CycleError):
            delivery_order({"a": ["b"], "b": ["a"]})


if __name__ == "__main__":
    unittest.main()
