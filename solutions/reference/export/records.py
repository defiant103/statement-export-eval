"""The rows the export works with, the same whichever core they came from."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Transaction:
    id: str
    date: str          # ISO date, YYYY-MM-DD
    description: str
    cents: int         # signed, from the member's point of view


@dataclass(frozen=True)
class Hold:
    id: str
    placed: str        # ISO date
    reason: str
    cents: int
