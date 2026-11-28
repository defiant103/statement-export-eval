"""Builds the month-end statement export for one member.

The output is diffed byte for byte by the reconciliation job downstream, so the
format below must not change.
"""
import csv
import io

from .errors import ExportError
from .jedha_client import JedhaClient
from .money import format_cents
from .scarif_client import ScarifClient


def build_statement(member_id, period, *, directory, jedha, scarif=None):
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
        if core == "JEDHA":
            readers.append((account_id, JedhaClient(jedha)))
        elif core == "SCARIF":
            if scarif is None:
                raise ExportError(f"account {account_id} is on Scarif and no Scarif transport was given", account_id)
            readers.append((account_id, ScarifClient(scarif)))
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
