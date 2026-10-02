"""
Pricing rules
=============
This is the ONLY place in the backend that decides what an order costs.

Why a single module?
-------------------
The browser used to repeat these numbers to show a total on the checkout page.
That meant the shop could quote a customer one price and store a different one
in the database. Money rules now live here and nowhere else; the checkout page
asks the server for a quote via `POST /api/orders/quote` and displays whatever
comes back, so the number the customer sees is by construction the number that
gets saved.
"""

from decimal import ROUND_HALF_UP, Decimal

# Flat delivery charge, waived once the basket is big enough.
SHIPPING_FLAT_RATE = Decimal("6.95")
FREE_SHIPPING_THRESHOLD = Decimal("100.00")

# Sales tax as a fraction of the goods subtotal.
TAX_RATE = Decimal("0.0825")

# Rounding is fixed to 2 decimal places the way a till would, rather than
# trusting binary floating point.
CENTS = Decimal("0.01")


def money(value) -> float:
    """Round a value to 2dp using normal half-up rules and return a float.

    `Decimal(str(value))` rather than `Decimal(value)`: the float 1.005 is
    really 1.00499999999999989... in binary, so converting it directly would
    round *down* to 1.00 and quietly lose a half cent. Going via `str` gives
    the decimal the number was meant to be.

    Floats are returned because that is what the database column and the JSON
    payload use. All intermediate arithmetic is Decimal, so rounding happens
    once, deliberately, instead of accumulating float error.
    """
    return float(Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP))


def shipping_for(subtotal: float) -> float:
    """Delivery cost for a goods subtotal. Free at or above the threshold."""
    subtotal = Decimal(str(subtotal))
    if subtotal <= 0 or subtotal >= FREE_SHIPPING_THRESHOLD:
        return 0.0
    return money(SHIPPING_FLAT_RATE)


def tax_for(subtotal: float) -> float:
    """Sales tax on the goods subtotal."""
    return money(Decimal(str(subtotal)) * TAX_RATE)


def quote(subtotal: float) -> dict:
    """Full price breakdown for a goods subtotal.

    Returns the figures as floats so they can be sent straight to the browser
    or stored on an order row.
    """
    subtotal = money(subtotal)
    shipping = shipping_for(subtotal)
    tax = tax_for(subtotal)
    return {
        "subtotal": subtotal,
        "shipping": shipping,
        "tax": tax,
        "total": money(subtotal + shipping + tax),
    }
