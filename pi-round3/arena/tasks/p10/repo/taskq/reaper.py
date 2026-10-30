from .models import State


def requeue_stale(store, now, timeout):
    """Put jobs that have been `running` for longer than `timeout` seconds back in the queue.  Returns how many."""
    count = 0
    for job in store.by_state(State.RUNNING):
        if job.started_at is not None and now - job.started_at > timeout:
            job.state = State.QUEUED
            job.run_at = now
            count += 1
    return count
