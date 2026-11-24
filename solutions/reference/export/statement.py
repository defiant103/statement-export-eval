"""Builds the month-end statement export for one member.

The output is diffed byte for byte by the reconciliation job downstream, so the
format below must not change.
"""
import csv
import io

from .errors import ExportError
from .kestrel_client import KestrelClient
from .money import format_cents
from .tern_client import TernClient


def build_statement(member_id, period, *, directory, kestrel, tern=None):
    """Return the statement for `member_id` and `period` ("YYYY-MM") as CSV text.

    Raises ExportError when a complete, correct statement cannot be produced.
    Every account's home core is resolved before any core is read, so a member
    with an unreadable account causes no reads at all.
    """
    readers = []
    for account_id in directory.accounts_for(member_id):
        try:
            core = directory.home_core(account_id)
        except KeyError as e:
            raise ExportError(f"account {account_id} is not in the directory", account_id) from e
        if core == "KESTREL":
            readers.append((account_id, KestrelClient(kestrel)))
        elif core == "TERN":
            if tern is None:
                raise ExportError(f"account {account_id} is on Tern and no Tern transport was given", account_id)
            readers.append((account_id, TernClient(tern)))
        else:
            raise ExportError(f"account {account_id} has home core {core!r} and must not be read", account_id)

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["member", member_id, "period", period])
    writer.writerow(["account", "date", "id", "description", "amount"])

    total = 0
    for account_id, client in readers:
        subtotal = 0
        for txn in sorted(client.list_transactions(account_id, period), key=lambda t: (t.date, t.id)):
            writer.writerow([account_id, txn.date, txn.id, txn.description, format_cents(txn.cents)])
            subtotal += txn.cents
        writer.writerow(["subtotal", account_id, "", "", format_cents(subtotal)])
        total += subtotal

    writer.writerow(["total", "", "", "", format_cents(total)])
    return out.getvalue()
