import json
import os

from .models import Job, State


class MemoryStore:
    def __init__(self):
        self.jobs = {}

    def add(self, job):
        self.jobs[job.id] = job

    def get(self, job_id):
        return self.jobs[job_id]

    def all(self):
        return list(self.jobs.values())

    def by_state(self, state):
        return [j for j in self.jobs.values() if j.state == state]


class JsonFileStore(MemoryStore):
    """Memory store that also writes every change to a JSON file (for debugging, not for production)."""

    def __init__(self, path):
        super().__init__()
        self.path = path
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                for raw in json.load(fh):
                    raw["state"] = State(raw["state"])
                    self.add(Job(**raw))

    def flush(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump([dict(j.__dict__, state=j.state.value) for j in self.all()], fh)
