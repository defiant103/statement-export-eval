"""The daily holds report for the branch operations team."""
import csv
import io

from .jedha_client import JedhaClient


def build_holds_report(member_id, *, directory, jedha):
    """Return the member's current holds on Jedha accounts as CSV text.

    Holds on Scarif accounts are reported by Scarif's own tooling and are not part
    of this report.
    """
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["account", "placed", "id", "reason", "amount"])
    for account_id in directory.accounts_for(member_id):
        if directory.home_core(account_id) != "JEDHA":
            continue
        holds = JedhaClient(jedha).list_holds(account_id)
        for hold in sorted(holds, key=lambda h: (h.placed, h.id)):
            writer.writerow([account_id, hold.placed, hold.id, hold.reason, f"{hold.amount:.2f}"])
    return out.getvalue()
