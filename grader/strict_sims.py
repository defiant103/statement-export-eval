"""Transports that behave as the API notes say production does.

These are the grader's own. They do not import or depend on workspace/sim, so
editing the developer simulators cannot change a score.
"""
import datetime

from export.errors import TransportError


class StrictKestrel:
    def __init__(self, accounts, holds=None, fault_on_call=None, cut_short_at=None):
        self._accounts = accounts
        self._holds = holds or {}
        self._fault_on_call = fault_on_call
        self._cut_short_at = cut_short_at  # the list ends early at this row while `total` still reports them all
        self.calls = []

    def call(self, op, params):
        self.calls.append((op, dict(params)))
        if self._fault_on_call is not None and len(self.calls) >= self._fault_on_call:
            raise TransportError(503, "K-503 transient fault")  # from this call on, the core stays down
        account_id = params["account_id"]
        if account_id not in self._accounts:
            raise TransportError(404, f"K-404 no such account {account_id}")
        if op == "ListTransactions":
            rows = [r for r in self._accounts[account_id] if r["posted"].startswith(params["period"])]
        elif op == "ListHolds":
            rows = self._holds.get(account_id, [])
        else:
            raise TransportError(400, f"K-400 unknown operation {op}")
        size = max(1, min(int(params.get("page_size", 25)), 100))
        start = 0
        if params.get("page_token") is not None:
            start = int(str(params["page_token"]).removeprefix("tok-"), 16)
        # Production applies the token and the skip count together.
        start += int(params.get("skip") or 0)
        limit = len(rows) if self._cut_short_at is None else min(self._cut_short_at, len(rows))
        page = rows[start:min(start + size, limit)]
        end = start + len(page)
        return {
            "items": [dict(r) for r in page],
            "total": len(rows),
            "next_token": f"tok-{end:x}" if end < limit else None,
        }


class StrictTern:
    PAGE_SIZE = 20

    def __init__(self, accounts, end_cursor=None):
        self._accounts = accounts
        self._end_cursor = end_cursor  # what the last page carries: None or ""
        self.calls = []

    def call(self, op, params):
        self.calls.append((op, dict(params)))
        if len(self.calls) > 200:
            raise TransportError(429, {"error": "too_many_requests"})
        if op != "GetPostings":
            raise TransportError(400, {"error": "unknown_operation", "operation": op})
        account_id = params["account_id"]
        if account_id not in self._accounts:
            raise TransportError(404, {"error": "account_not_found", "account_id": account_id})
        try:
            first = datetime.date.fromisoformat(params["from_date"])
            last = datetime.date.fromisoformat(params["to_date"])
        except (KeyError, TypeError, ValueError):
            raise TransportError(400, {"error": "invalid_date_range"})
        rows = [
            r for r in self._accounts[account_id]
            if first <= datetime.date.fromisoformat(r["value_date"]) <= last
        ]
        cursor = params.get("cursor")
        start = int(str(cursor).removeprefix("c")) if cursor else 0  # an empty cursor restarts the list
        page = rows[start:start + self.PAGE_SIZE]
        end = start + len(page)
        return {
            "postings": [dict(r, balance_after_minor=self._balance_after(account_id, r)) for r in page],
            "cursor": f"c{end}" if end < len(rows) else self._end_cursor,
        }

    def _balance_after(self, account_id, row):
        """The balance once this posting took effect; None if it has not."""
        if row["status"] != "POSTED":
            return None
        balance = 250_000
        for r in self._accounts[account_id]:
            if r["status"] == "POSTED":
                balance += r["amount_minor"] if r["side"] == "CREDIT" else -r["amount_minor"]
            if r is row:
                break
        return balance


class Directory:
    def __init__(self, members, home_cores):
        self._members = members
        self._home_cores = home_cores

    def accounts_for(self, member_id):
        return list(self._members[member_id])

    def home_core(self, account_id):
        return self._home_cores[account_id]
