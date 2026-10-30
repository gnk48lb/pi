from .errors import UnknownHandler

_registry = {}


def register(name, func):
    _registry[name] = func


def get(name):
    try:
        return _registry[name]
    except KeyError:
        raise UnknownHandler(name)
