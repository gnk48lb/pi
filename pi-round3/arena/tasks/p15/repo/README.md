# relay

Small helpers of a notification relay. They are meant to be **deterministic**: the same input gives the same output in
every run, on every machine, whatever the interpreter's hash seed (`PYTHONHASHSEED`) is. The rules below are the
specification.

```python
from relay import unique, delivery_order, CycleError, shard_for, summary, Router
```

## `unique(items)`

Returns a list with the distinct items of the iterable `items` (they are hashable), each one exactly once, **in order of
first appearance**: `unique(["b", "a", "b", "c", "a"])` is `["b", "a", "c"]`.

## `delivery_order(deps)`

`deps` maps a channel name to an iterable of the channels that must be delivered before it. A channel that only appears
as a dependency is a channel without dependencies of its own. The result is a list that contains every channel exactly
once, each channel after all of its dependencies.

When several channels are ready at the same time, they are delivered **one at a time, always the alphabetically smallest
ready channel first** (plain string comparison). Example: `{"a": ["b"], "c": []}` gives `["b", "a", "c"]`: once `b` is
delivered, `a` is ready and smaller than `c`.

If the dependencies contain a cycle, `CycleError` is raised. Its message is `dependency cycle among: ` followed by every
channel that could not be scheduled (the members of the cycle and the channels that wait for them), in alphabetical
order, joined by `", "`: `dependency cycle among: a, b, c`.

## `shard_for(key, shards)`

The number of the shard that stores `key`: the CRC-32 (`zlib.crc32`) of the key's UTF-8 bytes (a `bytes` key is used as it
is), modulo `shards`. Shard numbers are written to files, so the answer must be the same in every process, on every
machine and in every Python version. `shards` must be an integer >= 1, otherwise `ValueError` is raised.

## `summary(events)`

`events` is an iterable of dicts with the keys `region` (a string) and `ms` (a number). The result is a text with one line
per region, **in order of the region's first appearance**, lines joined by `"\n"`:

```
<region>: <n> events, avg <mean> ms
```

`<mean>` is the mean of the region's `ms` values with one decimal (`format(x, ".1f")`); the word is always `events`.
With no events at all the result is `no events`.

## `Router`

* `subscribe(topic, who)` adds a subscriber to a topic (subscribing twice has no further effect);
  `unsubscribe(topic, who)` removes one (nothing happens if `who` is not subscribed).
* `recipients(topic)` returns the subscribers of the topic as a list, **alphabetically**; an unknown topic has none.
* `topics()` returns every topic that was ever subscribed to, **in order of its first subscription**. A topic stays in the
  list when all of its subscribers have left.

## Tests

`python3 -m unittest` runs the tests in `tests/`. They cover the basics only.
