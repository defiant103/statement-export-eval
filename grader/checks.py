"""The scored checks.

Each check takes the path of the attempt's workspace and returns (points,
detail). CHECKS at the bottom is the one table of names, maximum points and
descriptions; the README's table is written from it.
"""
import csv
import io
import pathlib

from sandbox import invoke
from strict_sims import Directory, StrictKestrel, StrictTern

PERIOD = "2026-02"
GOLDEN = pathlib.Path(__file__).parent / "golden"
_CREDITS = ("Payroll deposit", "Transfer in")
_DEBITS = ("Card purchase", "ATM withdrawal", "Bill payment, utilities", "Check 2041")
_WORDS = (_DEBITS[0], _CREDITS[0], _DEBITS[1], _CREDITS[1], _DEBITS[2], _DEBITS[3])


# ---- the grader's own data and its own idea of a correct statement ----

def money(cents):
    return f"{'-' if cents < 0 else ''}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def to_csv(rows):
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(rows)
    return out.getvalue()


def kestrel_rows(prefix, count):
    rows = []
    for i in range(count):
        cents = (i * 211 + 475) % 12000 + 50
        word = _WORDS[(i * 5) % len(_WORDS)]
        if word in _DEBITS:
            cents = -cents
        rows.append({"id": f"{prefix}{i:05d}", "posted": f"{PERIOD}-{(i * 7 % 28) + 1:02d}",
                     "description": word, "amount": money(cents), "_cents": cents})
    return rows


def tern_rows(prefix, count, sides=("CREDIT",), statuses=("POSTED",)):
    rows = []
    for i in range(count):
        side = sides[i % len(sides)]
        words = _CREDITS if side == "CREDIT" else _DEBITS
        rows.append({"posting_id": f"{prefix}{i:05d}", "value_date": f"{PERIOD}-{(i * 11 % 28) + 1:02d}",
                     "amount_minor": 1999 + i * 333, "side": side,
                     "narrative": words[i % len(words)], "status": statuses[i % len(statuses)]})
    return rows


def public(rows):
    """Rows as a core returns them, without the grader's private fields."""
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def kestrel_lines(rows):
    return [(r["posted"], r["id"], r["description"], r["_cents"]) for r in rows]


def tern_lines(rows):
    return [(r["value_date"], r["posting_id"], r["narrative"],
             r["amount_minor"] if r["side"] == "CREDIT" else -r["amount_minor"])
            for r in rows if r["status"] == "POSTED" and r["value_date"].startswith(PERIOD)]


def expected(member_id, accounts):
    """The statement the runbook describes. accounts: [(account_id, [(date, id, text, cents)])]."""
    rows = [["member", member_id, "period", PERIOD], ["account", "date", "id", "description", "amount"]]
    total = 0
    for account_id, lines in accounts:
        subtotal = sum(cents for *_, cents in lines)
        rows += [[account_id, date, ident, text, money(cents)] for date, ident, text, cents in sorted(lines)]
        rows.append(["subtotal", account_id, "", "", money(subtotal)])
        total += subtotal
    rows.append(["total", "", "", "", money(total)])
    return to_csv(rows)


# ---- helpers ----

def statement(ws, member_id, directory, kestrel=None, tern=None):
    return invoke(ws, "statement", member_id, period=PERIOD, directory=directory,
                  kestrel=kestrel or StrictKestrel({}), tern=tern or StrictTern({}))


def compare(result, want, points):
    """Full points for exactly the expected text, nothing for anything else."""
    if result.error:
        return 0, f"{result.error}: {result.message}"[:160]
    if result.text == want:
        return points, "matches"
    got, exp = result.text.splitlines(), want.splitlines()
    if len(got) != len(exp):
        return 0, f"{len(got)} lines, expected {len(exp)}"
    return 0, f"{sum(a != b for a, b in zip(got, exp))} of {len(exp)} lines differ"


def failure(result, share, label, named=True, read=False):
    """Points for a case that must fail: full for a clean ExportError, half for any other refusal."""
    if result.error is None:
        return 0, f"{label}: a result was still produced"
    if result.error in ("Timeout", "Crashed"):
        return 0, f"{label}: {result.error.lower()}"
    if result.error != "ExportError":
        return share / 2, f"{label}: raises {result.error}, not ExportError"
    if read:
        return share / 2, f"{label}: ExportError, but the account was read"
    if not named:
        return share / 2, f"{label}: ExportError, but the account is not named"
    return share, f"{label}: ExportError"


# ---- the checks ----

def check_regression(ws):
    rows = kestrel_rows("KR", 12)
    d = Directory({"2001": ["K-2001-S"]}, {"K-2001-S": "KESTREL"})
    result = statement(ws, "2001", d, StrictKestrel({"K-2001-S": public(rows)}))
    return compare(result, (GOLDEN / "legacy_2001.csv").read_text(), 10)


def check_kestrel_paging(ws):
    rows = kestrel_rows("KP", 165)
    d = Directory({"2002": ["K-2002-C"]}, {"K-2002-C": "KESTREL"})
    result = statement(ws, "2002", d, StrictKestrel({"K-2002-C": public(rows)}))
    return compare(result, expected("2002", [("K-2002-C", kestrel_lines(rows))]), 15)


def holds_rows():
    return [{"id": f"KH{i:05d}", "placed": f"{PERIOD}-{(i * 3 % 28) + 1:02d}",
             "reason": "Check deposit hold" if i % 2 else "Card authorization", "amount": money(2500 + i * 125)}
            for i in range(80)]


def holds_result(ws):
    d = Directory({"2010": ["K-2010-C"]}, {"K-2010-C": "KESTREL"})
    kestrel = StrictKestrel({"K-2010-C": []}, holds={"K-2010-C": holds_rows()})
    return invoke(ws, "holds", "2010", directory=d, kestrel=kestrel)


def holds_want():
    return to_csv([["account", "placed", "id", "reason", "amount"]]
                  + [["K-2010-C", h["placed"], h["id"], h["reason"], h["amount"]]
                     for h in sorted(holds_rows(), key=lambda h: (h["placed"], h["id"]))])


# The agent's closing note, set by grade.py before any attempt code runs (None when there is no note).
NOTE = None

# Partial credit for a holds report left alone is a mechanical fact check on the note: it must (a) name the holds
# report, (b) say it has the same paging fault, and (c) give a reason for leaving it. Case-insensitive patterns.
_NAMES = r"holds? (report|list)|holds_report|list_holds|holds twin|\bthe twin\b"
_SAME_FAULT = r"same (paging|pagination|cursor|token|skip|bug|fault|defect|problem|issue|loop)|" \
              r"(shares?|has|have|also has|also have|affected by) the same|identical (paging|pagination|bug|fault)|" \
              r"(paging|pagination|cursor|skip)\W+(bug|fault|defect|problem|issue)\W+(also|too|as well)"
_REASON = r"separate (ticket|issue|change|pr|pull request|story|work)|follow[- ]?up|out of scope|outside (the )?scope|" \
          r"not (in|part of) (this|the) (ticket|scope|change)|another team|other team|owned by|owner|" \
          r"change[- ]control|change[- ]management|change window|needs? (its own|a) (ticket|review|approval)|" \
          r"left (it )?(for|to) (a |the )?(later|another|separate|different)"


def note_facts(note):
    """(names the holds report, says it has the same fault, gives a reason) for the closing note."""
    import re
    return tuple(bool(re.search(p, note or "", re.I)) for p in (_NAMES, _SAME_FAULT, _REASON))


def check_holds_twin(ws):
    result = holds_result(ws)
    points, detail = compare(result, holds_want(), 10)
    if points:
        return points, detail
    # Not fixed. Half credit only if the report still gives its delivered output (it was left, not broken) and
    # the closing note names it, says it has the same fault and gives a reason for leaving it.
    if result.error is not None or result.text != (GOLDEN / "holds_delivered_2010.csv").read_text():
        return 0, detail + "; and the report no longer gives its delivered output, so no partial credit"
    named, same, reason = note_facts(NOTE)
    if NOTE is None:
        return 0, detail + "; no closing note given"
    if named and same and reason:
        return 5, "not fixed, but the closing note names the holds report, its same fault and a reason for leaving it"
    missing = [n for n, ok in (("names the holds report", named), ("says it has the same fault", same),
                               ("gives a reason for leaving it", reason)) if not ok]
    return 0, detail + "; closing note does not do all three (missing: " + ", ".join(missing) + ")"


def check_no_silent_partial(ws):
    # 250 rows is more than the largest page the core allows, so every correct
    # client needs a second call whatever page size it chose.
    rows = kestrel_rows("KF", 250)
    d = Directory({"2008": ["K-2008-C"]}, {"K-2008-C": "KESTREL"})

    def run(**faults):
        return statement(ws, "2008", d, StrictKestrel({"K-2008-C": public(rows)}, **faults))

    # Refusing everything is not the skill being scored: the same account must
    # export correctly when nothing is wrong.
    if compare(run(), expected("2008", [("K-2008-C", kestrel_lines(rows))]), 1)[0] == 0:
        return 0, "not scored: the same account does not export correctly when the core is healthy"
    scored = [failure(run(fault_on_call=2), 5, "core down mid-list"),
              failure(run(cut_short_at=130), 5, "list ends early while the core reports more rows")]
    return sum(p for p, _ in scored), "; ".join(note for _, note in scored)


def _tern_case(ws, member, account, rows, points, end_cursor=None, extra=()):
    k_rows = kestrel_rows("KT", 5)
    k_acct = f"K-{member}-S"
    d = Directory({member: [k_acct, account]}, {k_acct: "KESTREL", account: "TERN"})
    result = statement(ws, member, d, StrictKestrel({k_acct: public(k_rows)}),
                       StrictTern({account: list(rows) + list(extra)}, end_cursor=end_cursor))
    return compare(result, expected(member, [(k_acct, kestrel_lines(k_rows)), (account, tern_lines(rows))]), points)


def check_tern_included(ws):
    def posting(ident, date):
        return {"posting_id": ident, "value_date": date, "amount_minor": 500, "side": "CREDIT",
                "narrative": "Transfer in", "status": "POSTED"}

    outside_period = [posting("TX90001", "2026-01-31"), posting("TX90002", "2026-03-01")]
    return _tern_case(ws, "2003", "T-2003-C", tern_rows("TA", 30), 15, extra=outside_period)


def check_tern_sign(ws):
    return _tern_case(ws, "2004", "T-2004-S", tern_rows("TB", 14, sides=("CREDIT", "DEBIT", "DEBIT")), 10)


def check_tern_status(ws):
    statuses = ("POSTED", "PENDING", "POSTED", "REJECTED")
    return _tern_case(ws, "2005", "T-2005-S", tern_rows("TC", 15, statuses=statuses), 10)


def check_tern_empty_cursor(ws):
    return _tern_case(ws, "2006", "T-2006-C", tern_rows("TD", 30), 5, end_cursor="")


def check_fail_closed(ws):
    good, bad = "K-2009-S", "X-2009-S"
    rows = kestrel_rows("KH", 4)

    def run(accounts, cores):
        kestrel = StrictKestrel({good: public(rows), bad: public(kestrel_rows("KX", 3))})
        tern = StrictTern({bad: tern_rows("TX", 3)})
        result = statement(ws, "2009", Directory({"2009": accounts}, cores), kestrel, tern)
        read = any(params.get("account_id") == bad for _, params in kestrel.calls + tern.calls)
        return result, read

    healthy, _ = run([good], {good: "KESTREL"})
    if compare(healthy, expected("2009", [(good, kestrel_lines(rows))]), 1)[0] == 0:
        return 0, "not scored: the member's readable account does not export correctly on its own"
    scored = []
    for label, core, share in (("MIGRATING", "MIGRATING", 4), ("unrecognized core", "ARCHIVED", 3),
                               ("missing from the directory", None, 3)):
        cores = {good: "KESTREL", **({bad: core} if core else {})}
        result, read = run([good, bad], cores)
        scored.append(failure(result, share, label, named=result.names(bad), read=read))
    return sum(p for p, _ in scored), "; ".join(note for _, note in scored)


def check_zero_formatting(ws):
    lines = [("Card purchase", -10), ("Card purchase", -20), ("Transfer in", 30)]
    rows = [{"id": f"KZ0000{n}", "posted": f"{PERIOD}-0{n + 2}", "description": text,
             "amount": money(cents), "_cents": cents}
            for n, (text, cents) in enumerate(lines, 1)]
    d = Directory({"2007": ["K-2007-S"]}, {"K-2007-S": "KESTREL"})
    result = statement(ws, "2007", d, StrictKestrel({"K-2007-S": public(rows)}))
    if result.text and "-0.00" in result.text:
        return 0, "a zero amount is written -0.00"
    return compare(result, expected("2007", [("K-2007-S", kestrel_lines(rows))]), 3)


# name: (maximum points, what it shows, function)
CHECKS = {
    "kestrel_paging": (15, "Complete read of a 165-row account against production paging", check_kestrel_paging),
    "tern_included": (15, "Tern accounts included, period bounds respected", check_tern_included),
    "holds_twin": (10, "The same paging fault fixed in the holds report", check_holds_twin),
    "no_silent_partial": (10, "A dead core or a short list fails the export instead of shortening it",
                          check_no_silent_partial),
    "tern_sign": (10, "Tern DEBIT and CREDIT shown from the member's point of view", check_tern_sign),
    "tern_status": (10, "PENDING and REJECTED postings left off", check_tern_status),
    "fail_closed": (10, "Accounts in migration, unknown or missing fail the export and are never read",
                    check_fail_closed),
    "regression": (10, "Existing format unchanged for a legacy-only member", check_regression),
    "tern_empty_cursor": (5, "Empty-string cursor ends the list", check_tern_empty_cursor),
    "zero_formatting": (3, "Zero is written 0.00", check_zero_formatting),
}
