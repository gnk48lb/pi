import time

from . import handlers, metrics, reaper, settings
from .errors import FatalJobError


class Worker:
    def __init__(self, queue, clock=time.time, sleep=time.sleep):
        self.queue = queue
        self.clock = clock
        self.sleep = sleep
        self.stopped = False

    def run_once(self):
        job = self.queue.dequeue()
        if job is None:
            return False
        try:
            handlers.get(job.handler)(job.payload)
        except FatalJobError as err:
            self.queue.bury(job, err)
            metrics.count("dead")
        except Exception as err:  # noqa: BLE001 - any handler error is a job failure
            self.queue.fail(job, err)
            metrics.count("failed")
        else:
            self.queue.complete(job)
            metrics.count("done")
        return True

    def run_forever(self):
        last_reap = self.clock()
        while not self.stopped:
            # reap stale jobs once a minute
            if self.clock() - last_reap >= settings.REAP_INTERVAL:
                reaper.requeue_stale(self.queue.store, self.clock(), settings.VISIBILITY_TIMEOUT)
                last_reap = self.clock()
            if not self.run_once():
                self.sleep(settings.POLL_INTERVAL)
