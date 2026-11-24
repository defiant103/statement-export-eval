"""Developer simulator for the Kestrel core. Shared with other teams: do not modify."""
from export.errors import TransportError


class KestrelSim:
    def __init__(self, accounts, holds=None):
        self._accounts = accounts    # account_id -> [ {id, posted, description, amount}, ... ]
        self._holds = holds or {}    # account_id -> [ {id, placed, reason, amount}, ... ]

    def call(self, op, params):
        account_id = params["account_id"]
        if account_id not in self._accounts:
            raise TransportError(404, f"K-404 no such account {account_id}")
        if op == "ListTransactions":
            rows = [r for r in self._accounts[account_id] if r["posted"].startswith(params["period"])]
        elif op == "ListHolds":
            rows = self._holds.get(account_id, [])
        else:
            raise TransportError(400, f"K-400 unknown operation {op}")
        size = int(params.get("page_size", 25))
        if params.get("page_token") is not None:
            start = int(params["page_token"])
        else:
            start = int(params.get("skip", 0))
        page = rows[start:start + size]
        end = start + len(page)
        return {
            "items": [dict(r) for r in page],
            "total": len(rows),
            "next_token": str(end) if end < len(rows) else None,
        }
