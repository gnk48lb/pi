import unittest

from taskq import handlers
from taskq.errors import FatalJobError
from taskq.models import State
from taskq.queue import Queue
from taskq.store import MemoryStore
from taskq.worker import Worker


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.queue = Queue(MemoryStore(), clock=lambda: 0.0)
        self.worker = Worker(self.queue, clock=lambda: 0.0, sleep=lambda s: None)

    def test_success(self):
        handlers.register("ok", lambda payload: None)
        job = self.queue.enqueue("ok")
        self.assertTrue(self.worker.run_once())
        self.assertEqual(job.state, State.DONE)

    def test_idle(self):
        self.assertFalse(self.worker.run_once())

    def test_fatal_error_is_not_retried(self):
        def boom(payload):
            raise FatalJobError("no")
        handlers.register("boom", boom)
        job = self.queue.enqueue("boom")
        self.worker.run_once()
        self.assertEqual(job.state, State.DEAD)
