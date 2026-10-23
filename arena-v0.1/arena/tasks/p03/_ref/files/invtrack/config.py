"""Settings that can be overridden by the host application."""

# Name of the function in invtrack.pricing that prices an order.  Applications that
# ship their own pricing module set this before calling the command line entry point.
PRICING_FUNCTION = "compute_order_total"

DEFAULT_TAX = 0.0
