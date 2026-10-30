"""Runtime settings.  Most can be overridden with environment variables."""
import os


def _env_int(name, default):
    raw = os.environ.get(name)
    return int(raw) if raw else default


DEFAULT_MAX_ATTEMPTS = _env_int("TASKQ_MAX_ATTEMPTS", 5)

BACKOFF_BASE = 1.5
BACKOFF_FACTOR = 3.0
BACKOFF_CAP = 30.0

VISIBILITY_TIMEOUT = 120.0     # seconds a job may stay in `running` before it counts as stuck
REAP_INTERVAL = 30.0
POLL_INTERVAL = 0.5

METRICS_ENABLED = True
