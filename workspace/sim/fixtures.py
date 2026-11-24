"""Fixture data for the developer simulators. Shared with other teams: do not modify."""
from export.directory import StaticDirectory

from .kestrel_sim import KestrelSim
from .tern_sim import TernSim

_DESCRIPTIONS = ["Card purchase", "Payroll deposit", "ATM withdrawal", "Transfer in", "Bill payment, utilities"]


def _kestrel_rows(prefix, count, period="2026-02"):
    rows = []
    for i in range(count):
        cents = (i * 137 + 250) % 9000 + 100
        description = _DESCRIPTIONS[i % len(_DESCRIPTIONS)]
        if description not in ("Payroll deposit", "Transfer in"):
            cents = -cents
        rows.append({
            "id": f"{prefix}{i:05d}",
            "posted": f"{period}-{(i % 27) + 1:02d}",
            "description": description,
            "amount": f"{'-' if cents < 0 else ''}{abs(cents) // 100}.{abs(cents) % 100:02d}",
        })
    return rows


def _tern_deposits(prefix, count, period="2026-02"):
    return [
        {
            "posting_id": f"{prefix}{i:05d}",
            "value_date": f"{period}-{(i * 5 % 27) + 1:02d}",
            "amount_minor": 12500 + i * 375,
            "side": "CREDIT",
            "narrative": "Payroll deposit" if i % 2 == 0 else "Transfer in",
        }
        for i in range(count)
    ]


def build():
    """Return (directory, kestrel_transport, tern_transport) for the dev fixtures."""
    directory = StaticDirectory(
        members={
            "1001": ["K-1001-S"],
            "1002": ["K-1002-C"],
            "1003": ["K-1003-S", "T-1003-C"],
        },
        home_cores={
            "K-1001-S": "KESTREL",
            "K-1002-C": "KESTREL",
            "K-1003-S": "KESTREL",
            "T-1003-C": "TERN",
        },
    )
    kestrel = KestrelSim(
        {
            "K-1001-S": _kestrel_rows("KA", 8),
            "K-1002-C": _kestrel_rows("KB", 60),
            "K-1003-S": _kestrel_rows("KC", 5),
        },
        holds={
            "K-1002-C": [
                {"id": f"KH{i:05d}", "placed": f"2026-02-{(i % 9) + 10:02d}",
                 "reason": "Check deposit hold" if i % 2 else "Card authorization", "amount": f"{40 + i * 3}.00"}
                for i in range(6)
            ],
        },
    )
    tern = TernSim({"T-1003-C": _tern_deposits("TP", 4)})
    return directory, kestrel, tern
