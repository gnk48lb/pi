import itertools
import time

from . import backoff, settings
from .models import Job, State

_ids = itertools.count(1)


class Queue:
    def __init__(self, store, clock=time.time):
        self.store = store
        self.clock = clock

    def enqueue(self, handler, payload=None, max_attempts=None, delay=0.0):
        job = Job(
            id="job-%d" % next(_ids),
            handler=handler,
            payload=dict(payload or {}),
            max_attempts=max_attempts or settings.DEFAULT_MAX_ATTEMPTS,
            run_at=self.clock() + delay,
        )
        self.store.add(job)
        return job

    def dequeue(self):
        now = self.clock()
        ready = [j for j in self.store.by_state(State.QUEUED) if j.run_at <= now]
        if not ready:
            return None
        job = min(ready, key=lambda j: (j.run_at, j.id))
        job.state = State.RUNNING
        job.started_at = now
        job.attempts += 1
        return job

    def complete(self, job):
        job.state = State.DONE
        job.last_error = None

    def fail(self, job, error):
        """An ordinary failure: retry later, or give up when the attempts are used up."""
        job.last_error = str(error)
        if job.attempts >= job.max_attempts:
            job.state = State.FAILED
            return
        wait = backoff.delay(job.attempts, settings.BACKOFF_BASE, settings.BACKOFF_FACTOR, settings.BACKOFF_CAP)
        job.state = State.QUEUED
        job.run_at = self.clock() + wait

    def bury(self, job, error):
        """A fatal failure: never retry."""
        job.last_error = str(error)
        job.state = State.DEAD
