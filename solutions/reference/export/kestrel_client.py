"""Client for the Kestrel core (the legacy core). See docs/kestrel-api-notes.md."""
from dataclasses import dataclass

from .errors import ExportError, TransportError
from .money import parse_decimal_cents

PAGE_SIZE = 25


@dataclass(frozen=True)
class Transaction:
    id: str
    date: str          # ISO date, YYYY-MM-DD
    description: str
    cents: int         # signed, from the member's point of view


@dataclass(frozen=True)
class Hold:
    id: str
    placed: str        # ISO date
    reason: str
    cents: int


class KestrelClient:
    def __init__(self, transport):
        self._transport = transport

    def _read_all(self, op, account_id, extra):
        """Read every row of a paged list, or raise ExportError.

        Pages are continued with the token alone. The production capture for
        STMT-212 shows the core applying a token and a skip count together: the
        second request carried the token for row 25 and skip=25, and the reply
        started at row 50. The read is then checked against the core's own row
        count, so a short list can never pass as complete.
        """
        items = []
        token = None
        total = None
        while True:
            params = {"account_id": account_id, "page_size": PAGE_SIZE, **extra}
            if token is not None:
                params["page_token"] = token
            try:
                reply = self._transport.call(op, params)
            except TransportError as e:
                raise ExportError(f"Kestrel {op} failed for account {account_id}: {e}", account_id) from e
            items.extend(reply["items"])
            total = reply.get("total", total)
            token = reply.get("next_token")
            if not token:
                break
            if not reply["items"]:
                raise ExportError(f"Kestrel {op} returned an empty page with more to come for account {account_id}", account_id)

        ids = [item["id"] for item in items]
        if len(set(ids)) != len(ids):
            raise ExportError(f"Kestrel {op} returned repeated rows for account {account_id}", account_id)
        if total is None or len(items) != total:
            raise ExportError(
                f"Kestrel {op} for account {account_id} is incomplete: {len(items)} rows read, core reports {total}",
                account_id)
        return items

    def list_transactions(self, account_id, period):
        """All of an account's transactions for a period ("YYYY-MM"), or ExportError."""
        items = self._read_all("ListTransactions", account_id, {"period": period})
        try:
            return [
                Transaction(id=item["id"], date=item["posted"], description=item["description"],
                            cents=parse_decimal_cents(item["amount"]))
                for item in items
            ]
        except (KeyError, ValueError) as e:
            raise ExportError(f"Kestrel returned a row the export cannot read for account {account_id}: {e}", account_id) from e

    def list_holds(self, account_id):
        """All holds currently placed on an account, or ExportError."""
        items = self._read_all("ListHolds", account_id, {})
        try:
            return [
                Hold(id=item["id"], placed=item["placed"], reason=item["reason"],
                     cents=parse_decimal_cents(item["amount"]))
                for item in items
            ]
        except (KeyError, ValueError) as e:
            raise ExportError(f"Kestrel returned a hold the report cannot read for account {account_id}: {e}", account_id) from e
