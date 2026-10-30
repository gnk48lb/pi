import unittest

from relay import Router


class RouterTests(unittest.TestCase):
    def test_subscribe_and_unsubscribe(self):
        router = Router()
        router.subscribe("alerts", "ann")
        self.assertEqual(router.recipients("alerts"), ["ann"])
        router.unsubscribe("alerts", "ann")
        self.assertEqual(router.recipients("alerts"), [])

    def test_unknown_topic_has_no_recipients(self):
        self.assertEqual(Router().recipients("nothing"), [])

    def test_topics(self):
        router = Router()
        router.subscribe("alerts", "ann")
        self.assertEqual(router.topics(), ["alerts"])


if __name__ == "__main__":
    unittest.main()
