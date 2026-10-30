# Operations

* Run one worker per CPU.  `Worker.run_forever()` polls the queue, runs the handler and records the result.
* Stuck jobs: a worker that dies leaves its job in `running`.  The reaper puts such jobs back in the queue; it runs
  about once a minute.
* Jobs that fail are retried with exponential backoff (1s, 2s, 4s, ...) until they run out of attempts.
* Metrics are exposed through `taskq.metrics.snapshot()`.
