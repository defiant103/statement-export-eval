"""Client for the Tern core."""
import calendar

from .kestrel_client import Transaction


class TernClient:
    def __init__(self, transport):
        self._transport = transport

    def list_transactions(self, account_id, period):
        year, month = (int(p) for p in period.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        params = {"account_id": account_id, "from_date": f"{period}-01", "to_date": f"{period}-{last_day:02d}"}
        postings = []
        while True:
            reply = self._transport.call("GetPostings", params)
            postings.extend(reply["postings"])
            if reply.get("cursor") is None:
                break
            params["cursor"] = reply["cursor"]
        return [
            Transaction(id=p["posting_id"], date=p["value_date"], description=p["narrative"],
                        amount=p["amount_minor"] / 100)
            for p in postings
        ]
