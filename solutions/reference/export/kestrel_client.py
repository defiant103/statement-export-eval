"""Client for the Kestrel core (the legacy core). See docs/kestrel-api-notes.md."""
from .errors import ExportError, TransportError
from .money import parse_decimal_cents
from .records import Hold, Transaction

PAGE_SIZE = 25


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
        def fail(problem):
            return ExportError(f"Kestrel {op} for account {account_id}: {problem}", account_id)

        items, token, total, seen_tokens = [], None, None, set()
        while True:
            params = {"account_id": account_id, "page_size": PAGE_SIZE, **extra}
            if token is not None:
                params["page_token"] = token
            try:
                reply = self._transport.call(op, params)
            except TransportError as e:
                raise fail(f"the core faulted ({e})") from e
            items.extend(reply["items"])
            total = reply.get("total", total)
            token = reply.get("next_token")
            if not token:
                break
            if not reply["items"] or token in seen_tokens:
                raise fail("the list stopped advancing before it ended")
            seen_tokens.add(token)

        if len({item["id"] for item in items}) != len(items):
            raise fail("rows were repeated")
        if total is None or len(items) != total:
            raise fail(f"incomplete read, {len(items)} rows of {total}")
        return items

    def list_transactions(self, account_id, period):
        """All of an account's transactions for a period ("YYYY-MM"), or ExportError."""
        items = self._read_all("ListTransactions", account_id, {"period": period})
        try:
            return [Transaction(id=item["id"], date=item["posted"], description=item["description"],
                                cents=parse_decimal_cents(item["amount"]))
                    for item in items]
        except (KeyError, ValueError) as e:
            raise ExportError(f"Kestrel returned an unreadable transaction for account {account_id}: {e}",
                              account_id) from e

    def list_holds(self, account_id):
        """All holds currently placed on an account, or ExportError."""
        items = self._read_all("ListHolds", account_id, {})
        try:
            return [Hold(id=item["id"], placed=item["placed"], reason=item["reason"],
                         cents=parse_decimal_cents(item["amount"]))
                    for item in items]
        except (KeyError, ValueError) as e:
            raise ExportError(f"Kestrel returned an unreadable hold for account {account_id}: {e}", account_id) from e
