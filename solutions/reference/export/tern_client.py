"""Client for the Tern core. See docs/tern-api-notes.md."""
import calendar

from .errors import ExportError, TransportError
from .kestrel_client import Transaction

MAX_PAGES = 10_000


class TernClient:
    def __init__(self, transport):
        self._transport = transport

    def list_transactions(self, account_id, period):
        """An account's POSTED postings for a period ("YYYY-MM"), signed for the member, or ExportError."""
        year, month = (int(part) for part in period.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        params = {"account_id": account_id, "from_date": f"{period}-01", "to_date": f"{period}-{last_day:02d}"}

        postings = []
        seen_cursors = set()
        for _ in range(MAX_PAGES):
            try:
                reply = self._transport.call("GetPostings", params)
            except TransportError as e:
                raise ExportError(f"Tern read failed for account {account_id}: {e}", account_id) from e
            postings.extend(reply["postings"])
            cursor = reply.get("cursor")
            if not cursor:  # absent, null or empty all mean the list has ended
                break
            if cursor in seen_cursors:
                raise ExportError(f"Tern repeated a cursor for account {account_id}", account_id)
            seen_cursors.add(cursor)
            params["cursor"] = cursor
        else:
            raise ExportError(f"Tern list for account {account_id} did not end", account_id)

        transactions = []
        seen_ids = set()
        for posting in postings:
            try:
                status, side, minor = posting["status"], posting["side"], posting["amount_minor"]
                if status in ("PENDING", "REJECTED"):
                    continue
                if status != "POSTED":
                    raise ValueError(f"unknown status {status!r}")
                if type(minor) is not int or minor < 0:
                    raise ValueError(f"bad amount_minor {minor!r}")
                if side == "CREDIT":      # in the production capture, balance_after rises by the amount on a CREDIT
                    cents = minor
                elif side == "DEBIT":
                    cents = -minor
                else:
                    raise ValueError(f"unknown side {side!r}")
                if posting["posting_id"] in seen_ids:
                    raise ValueError(f"repeated posting {posting['posting_id']}")
                seen_ids.add(posting["posting_id"])
                transactions.append(Transaction(id=posting["posting_id"], date=posting["value_date"],
                                                description=posting["narrative"], cents=cents))
            except (KeyError, ValueError) as e:
                raise ExportError(f"Tern returned a posting the export cannot read for account {account_id}: {e}", account_id) from e
        return transactions
