"""Regenerate workspace/logs/ by recording real calls against the grader's production-faithful transports.

Withheld from the agent, like everything else in grader/. Run from the repository root.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "grader"))
sys.path.insert(0, str(ROOT / "workspace"))

from export.errors import TransportError  # noqa: E402
from export.kestrel_client import KestrelClient  # noqa: E402
from strict_sims import StrictKestrel, StrictTern  # noqa: E402

LOGS = ROOT / "workspace" / "logs"
LOGS.mkdir(exist_ok=True)


class Recorder:
    def __init__(self, inner, core):
        self.inner, self.core, self.lines = inner, core, []

    def call(self, op, params):
        entry = {"seq": len(self.lines) + 1, "core": self.core, "op": op, "request": dict(params)}
        try:
            entry["response"] = self.inner.call(op, params)
            return entry["response"]
        except TransportError as e:
            entry["fault"] = {"status": e.status, "body": e.body}
            raise
        finally:
            self.lines.append(entry)

    def write(self, name, note=None):
        with open(LOGS / name, "w") as f:
            for line in self.lines:
                f.write(json.dumps(line) + "\n")
            if note:
                f.write(json.dumps({"note": note}) + "\n")


# --- Kestrel: the unmodified export code reading the busy checking account in production ---
words = ["Card purchase", "Payroll deposit", "ATM withdrawal", "Transfer in", "Bill payment, utilities"]
rows = []
for i in range(165):
    cents = (i * 173 + 310) % 8000 + 75
    word = words[i % len(words)]
    if word not in ("Payroll deposit", "Transfer in"):
        cents = -cents
    rows.append({"id": f"KQ{i:05d}", "posted": f"2026-02-{(i * 28 // 165) + 1:02d}", "description": word,
                 "amount": f"{'-' if cents < 0 else ''}{abs(cents) // 100}.{abs(cents) % 100:02d}"})
rec = Recorder(StrictKestrel({"K-10482-C": rows}), "kestrel")
got = KestrelClient(rec).list_transactions("K-10482-C", "2026-02")
assert len(got) == 75, len(got)
rec.write("prod-kestrel-2026-03-01.jsonl")

# --- Tern: the migration team's smoke-test script against production, which looped ---
postings = []
for i in range(29):
    postings.append({
        "posting_id": f"TS{i:05d}", "value_date": f"2026-02-{(i * 27 // 29) + 1:02d}",
        "amount_minor": 1500 + i * 425,
        "side": "CREDIT" if i % 4 in (0, 3) else "DEBIT",
        "narrative": ("Payroll deposit", "Transfer in")[i % 2] if i % 4 in (0, 3)
                     else ("Card purchase", "ATM withdrawal", "Bill payment, utilities")[i % 3],
        "status": "PENDING" if i in (7, 21) else "REJECTED" if i == 14 else "POSTED",
    })
rec = Recorder(StrictTern({"T-20031-S": postings}, end_cursor=""), "tern")
params = {"account_id": "T-20031-S", "from_date": "2026-02-01", "to_date": "2026-02-28"}
for _ in range(5):
    reply = rec.call("GetPostings", dict(params))
    if reply["cursor"] is None:
        break
    params["cursor"] = reply["cursor"]
rec.write("prod-tern-smoke-2026-02-20.jsonl", note="capture ends here: the script did not finish and was stopped by hand")
print("captures written")
