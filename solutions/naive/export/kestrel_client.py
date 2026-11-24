"""Client for the Kestrel core (the legacy core). See docs/kestrel-api-notes.md."""
from dataclasses import dataclass

from .errors import TransportError

PAGE_SIZE = 25


@dataclass(frozen=True)
class Hold:
    id: str
    placed: str        # ISO date
    reason: str
    amount: float


@dataclass(frozen=True)
class Transaction:
    id: str
    date: str          # ISO date, YYYY-MM-DD
    description: str
    amount: float      # signed, from the member's point of view


class KestrelClient:
    def __init__(self, transport):
        self._transport = transport

    def list_transactions(self, account_id, period):
        """All of an account's transactions for a period ("YYYY-MM")."""
        items = []
        token = None
        skip = 0
        while True:
            params = {"account_id": account_id, "period": period, "page_size": PAGE_SIZE}
            if token is not None:
                # Resume from where the last page ended. The skip count is sent
                # as well so a lost token cannot restart the list.
                params["page_token"] = token
                params["skip"] = skip
            try:
                reply = self._transport.call("ListTransactions", params)
            except TransportError:
                break  # return what we have rather than fail the whole run
            items.extend(reply["items"])
            skip += len(reply["items"])
            token = reply.get("next_token")
            if not token:
                break
        return [
            Transaction(
                id=item["id"],
                date=item["posted"],
                description=item["description"],
                amount=float(item["amount"]),
            )
            for item in items
        ]

    def list_holds(self, account_id):
        """All holds currently placed on an account."""
        items = []
        token = None
        skip = 0
        while True:
            params = {"account_id": account_id, "page_size": PAGE_SIZE}
            if token is not None:
                params["page_token"] = token
                params["skip"] = skip
            try:
                reply = self._transport.call("ListHolds", params)
            except TransportError:
                break
            items.extend(reply["items"])
            skip += len(reply["items"])
            token = reply.get("next_token")
            if not token:
                break
        return [
            Hold(id=item["id"], placed=item["placed"], reason=item["reason"], amount=float(item["amount"]))
            for item in items
        ]
