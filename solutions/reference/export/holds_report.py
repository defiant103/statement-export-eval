"""The daily holds report for the branch operations team."""
import csv
import io

from .kestrel_client import KestrelClient
from .money import format_cents


def build_holds_report(member_id, *, directory, kestrel):
    """Return the member's current holds on Kestrel accounts as CSV text.

    Holds on Tern accounts are reported by Tern's own tooling and are not part
    of this report.
    """
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["account", "placed", "id", "reason", "amount"])
    for account_id in directory.accounts_for(member_id):
        if directory.home_core(account_id) != "KESTREL":
            continue
        holds = KestrelClient(kestrel).list_holds(account_id)
        for hold in sorted(holds, key=lambda h: (h.placed, h.id)):
            writer.writerow([account_id, hold.placed, hold.id, hold.reason, format_cents(hold.cents)])
    return out.getvalue()
