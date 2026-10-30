"""Small helpers shared by the command line and the exporters."""
from . import config, pricing


def pricing_function(name=None):
    """Look up the configured pricing function."""
    return getattr(pricing, name or config.PRICING_FUNCTION)


def money(value):
    return "%.2f" % value
