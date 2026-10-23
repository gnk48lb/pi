import json


def dumps(job):
    return json.dumps({"id": job.id, "handler": job.handler, "payload": job.payload, "state": job.state.value})


def loads(text):
    return json.loads(text)
