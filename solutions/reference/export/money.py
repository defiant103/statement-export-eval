"""Amounts are integer cents everywhere inside the export."""
from decimal import Decimal, InvalidOperation


def parse_decimal_cents(text):
    """'-12.34' -> -1234. Raises ValueError unless the text is a whole number of cents."""
    try:
        cents = Decimal(text) * 100
    except (InvalidOperation, TypeError) as e:
        raise ValueError(f"not an amount: {text!r}") from e
    if cents != cents.to_integral_value():
        raise ValueError(f"not a whole number of cents: {text!r}")
    return int(cents)


def format_cents(cents):
    return f"{'-' if cents < 0 else ''}{abs(cents) // 100}.{abs(cents) % 100:02d}"
