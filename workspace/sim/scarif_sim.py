"""Developer simulator for the Scarif core. Shared with other teams: do not modify."""
import datetime

from export.errors import TransportError

PAGE_SIZE = 20


class ScarifSim:
    def __init__(self, accounts):
        self._accounts = accounts  # account_id -> [ {posting_id, value_date, amount_minor, side, narrative}, ... ]

    def call(self, op, params):
        if op != "GetPostings":
            raise TransportError(400, {"error": "unknown_operation", "operation": op})
        account_id = params["account_id"]
        if account_id not in self._accounts:
            raise TransportError(404, {"error": "account_not_found", "account_id": account_id})
        try:
            start_date = datetime.date.fromisoformat(params["from_date"])
            end_date = datetime.date.fromisoformat(params["to_date"])
        except (KeyError, ValueError):
            raise TransportError(400, {"error": "invalid_date_range"})
        rows = [
            r for r in self._accounts[account_id]
            if start_date <= datetime.date.fromisoformat(r["value_date"]) <= end_date
        ]
        start = int(params["cursor"]) if params.get("cursor") else 0
        page = rows[start:start + PAGE_SIZE]
        end = start + len(page)
        return {
            "postings": [dict(r, status="POSTED", balance_after_minor=self._balance_after(account_id, r))
                         for r in page],
            "cursor": str(end) if end < len(rows) else None,
        }

    def _balance_after(self, account_id, row):
        balance = 0
        for r in self._accounts[account_id]:
            balance += r["amount_minor"] if r["side"] == "CREDIT" else -r["amount_minor"]
            if r is row:
                return balance
        return balance
