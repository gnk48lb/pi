import unittest

from taskq.models import State
from taskq.queue import Queue
from taskq.store import MemoryStore


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.queue = Queue(MemoryStore(), clock=lambda: self.now)

    def test_dequeue_marks_running(self):
        job = self.queue.enqueue("h")
        got = self.queue.dequeue()
        self.assertIs(got, job)
        self.assertEqual((job.state, job.attempts), (State.RUNNING, 1))

    def test_nothing_ready(self):
        self.queue.enqueue("h", delay=10)
        self.assertIsNone(self.queue.dequeue())

    def test_complete(self):
        job = self.queue.enqueue("h")
        self.queue.dequeue()
        self.queue.complete(job)
        self.assertEqual(job.state, State.DONE)
