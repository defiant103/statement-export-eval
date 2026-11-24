"""Amounts are integer cents everywhere inside the export."""
import re

_AMOUNT = re.compile(r"(-?)(\d+)\.(\d\d)")


def parse_decimal_cents(text):
    """'-12.34' -> -1234. Raises ValueError for anything but digits, a point and two decimals."""
    match = _AMOUNT.fullmatch(text) if isinstance(text, str) else None
    if not match:
        raise ValueError(f"not an amount: {text!r}")
    sign, units, cents = match.groups()
    return (-1 if sign else 1) * (int(units) * 100 + int(cents))


def format_cents(cents):
    return f"{'-' if cents < 0 else ''}{abs(cents) // 100}.{abs(cents) % 100:02d}"
