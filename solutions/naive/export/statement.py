"""Builds the month-end statement export for one member.

The output is diffed byte for byte by the reconciliation job downstream, so the
format below must not change.
"""
import csv
import io

from .kestrel_client import KestrelClient
from .tern_client import TernClient


def build_statement(member_id, period, *, directory, kestrel, tern=None):
    """Return the statement for `member_id` and `period` ("YYYY-MM") as CSV text.

    `directory` answers accounts_for(member_id) and home_core(account_id).
    `kestrel` and `tern` are transports: objects with call(op, params) -> dict
    that raise TransportError on a fault.
    """
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["member", member_id, "period", period])
    writer.writerow(["account", "date", "id", "description", "amount"])

    total = 0.0
    for account_id in directory.accounts_for(member_id):
        core = directory.home_core(account_id)
        if core == "TERN":
            transactions = TernClient(tern).list_transactions(account_id, period)
        else:
            transactions = KestrelClient(kestrel).list_transactions(account_id, period)

        subtotal = 0.0
        for txn in sorted(transactions, key=lambda t: (t.date, t.id)):
            writer.writerow([account_id, txn.date, txn.id, txn.description, f"{txn.amount:.2f}"])
            subtotal += txn.amount
        writer.writerow(["subtotal", account_id, "", "", f"{subtotal:.2f}"])
        total += subtotal

    writer.writerow(["total", "", "", "", f"{total:.2f}"])
    return out.getvalue()
