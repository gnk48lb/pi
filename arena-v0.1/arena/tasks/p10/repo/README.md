# taskq

A small in-process job queue with retries, exponential backoff and a reaper for stuck jobs.

```python
from taskq.queue import Queue
from taskq.store import MemoryStore
from taskq.worker import Worker
from taskq import handlers

handlers.register("send_email", lambda payload: print("sending", payload))
queue = Queue(MemoryStore())
queue.enqueue("send_email", {"to": "a@example.com"})
Worker(queue).run_once()
```

## Configuration

Settings live in `taskq/settings.py`. The number of attempts a job gets can be changed with the environment variable
`TASKQ_RETRIES` (default 3).

## Operations

See `docs/operations.md`.

## Tests

`python3 -m unittest`
