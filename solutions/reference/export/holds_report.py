"""The daily holds report for the branch operations team."""
import csv
import io

from .errors import ExportError
from .kestrel_client import KestrelClient
from .money import format_cents


def build_holds_report(member_id, *, directory, kestrel):
    """Return the member's current holds on Kestrel accounts as CSV text, or raise ExportError.

    Holds on Tern accounts are reported by Tern's own tooling and are not part
    of this report. An account that is in migration, unknown or missing from the
    directory fails the report, as it fails a statement.
    """
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["account", "placed", "id", "reason", "amount"])
    for account_id in directory.accounts_for(member_id):
        try:
            core = directory.home_core(account_id)
        except KeyError as e:
            raise ExportError(f"account {account_id} is not in the directory", account_id) from e
        if core == "TERN":
            continue
        if core != "KESTREL":
            raise ExportError(f"account {account_id} has home core {core!r} and must not be read", account_id)
        holds = KestrelClient(kestrel).list_holds(account_id)
        for hold in sorted(holds, key=lambda h: (h.placed, h.id)):
            writer.writerow([account_id, hold.placed, hold.id, hold.reason, format_cents(hold.cents)])
    return out.getvalue()
