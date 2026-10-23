class ShopError(Exception):
    """Base class of the errors the API layer turns into HTTP-style statuses."""
    status = 500


class Invalid(ShopError):
    status = 400


class NotFound(ShopError):
    status = 404


class Conflict(ShopError):
    status = 409
