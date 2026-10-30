def shard_for(key, shards):
    """Number of the shard (0 <= n < shards) that stores `key`."""
    if shards < 1:
        raise ValueError("shards must be >= 1")
    return hash(key) % shards
