from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class State(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    DEAD = "dead"


@dataclass
class Job:
    id: str
    handler: str
    payload: dict = field(default_factory=dict)
    state: State = State.QUEUED
    attempts: int = 0
    max_attempts: int = 3
    run_at: float = 0.0
    started_at: Optional[float] = None
    last_error: Optional[str] = None
