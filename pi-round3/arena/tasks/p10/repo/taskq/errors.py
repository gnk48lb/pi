class TaskqError(Exception):
    """Base class of this package's errors."""


class FatalJobError(TaskqError):
    """Raised by a handler to say: do not retry this job, it can never succeed."""


class UnknownHandler(TaskqError):
    pass
