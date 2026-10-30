import unittest

from relay import shard_for


class ShardForTests(unittest.TestCase):
    def test_the_result_is_a_valid_shard_number(self):
        for key in ["alice", "bob", "carol", b"dave", "éve"]:
            self.assertIn(shard_for(key, 5), range(5))

    def test_the_same_key_always_gets_the_same_shard(self):
        self.assertEqual(shard_for("alice", 8), shard_for("alice", 8))

    def test_one_shard_means_shard_zero(self):
        self.assertEqual(shard_for("anything", 1), 0)

    def test_shards_must_be_positive(self):
        with self.assertRaises(ValueError):
            shard_for("alice", 0)


if __name__ == "__main__":
    unittest.main()
