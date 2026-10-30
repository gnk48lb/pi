import zlib


def shard_for(key, shards):
    """Number of the shard (0 <= n < shards) that stores `key`: stable across processes and machines."""
    if shards < 1:
        raise ValueError("shards must be >= 1")
    data = key if isinstance(key, bytes) else key.encode("utf-8")
    return zlib.crc32(data) % shards
