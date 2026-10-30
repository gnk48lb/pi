import logging

log = logging.getLogger("taskq")


def describe(job):
    return "%s[%s] attempt %d/%d" % (job.id, job.state.value, job.attempts, job.max_attempts)
