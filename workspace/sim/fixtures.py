"""Fixture data for the developer simulators. Shared with other teams: do not modify."""
from export.directory import StaticDirectory

from .jedha_sim import JedhaSim
from .scarif_sim import ScarifSim

_DESCRIPTIONS = ["Card purchase", "Payroll deposit", "ATM withdrawal", "Transfer in", "Bill payment, utilities"]


def _jedha_rows(prefix, count, period="2026-02"):
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


def _scarif_deposits(prefix, count, period="2026-02"):
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
    """Return (directory, jedha_transport, scarif_transport) for the dev fixtures."""
    directory = StaticDirectory(
        members={
            "1001": ["J-1001-S"],
            "1002": ["J-1002-C"],
            "1003": ["J-1003-S", "S-1003-C"],
        },
        home_cores={
            "J-1001-S": "JEDHA",
            "J-1002-C": "JEDHA",
            "J-1003-S": "JEDHA",
            "S-1003-C": "SCARIF",
        },
    )
    jedha = JedhaSim(
        {
            "J-1001-S": _jedha_rows("KA", 8),
            "J-1002-C": _jedha_rows("KB", 60),
            "J-1003-S": _jedha_rows("KC", 5),
        },
        holds={
            "J-1002-C": [
                {"id": f"KH{i:05d}", "placed": f"2026-02-{(i % 9) + 10:02d}",
                 "reason": "Check deposit hold" if i % 2 else "Card authorization", "amount": f"{40 + i * 3}.00"}
                for i in range(6)
            ],
        },
    )
    scarif = ScarifSim({"S-1003-C": _scarif_deposits("TP", 4)})
    return directory, jedha, scarif
