"""Currency conversion. Amounts are integer cents; the catalog is in euro cents."""

# units of the currency per euro, as (numerator, denominator)
RATES = {"EUR": (1, 1), "USD": (11, 10), "GBP": (17, 20), "CHF": (24, 25)}


def convert(eur_cents, currency):
    """Convert an amount in euro cents into cents of `currency`, rounding half up."""
    try:
        num, den = RATES[currency]
    except KeyError:
        raise ValueError("unknown currency: %s" % currency) from None
    return (2 * eur_cents * num + den) // (2 * den)


def format_money(cents, currency):
    """'USD 27.50'"""
    return "%s %d.%02d" % (currency, cents // 100, cents % 100)
