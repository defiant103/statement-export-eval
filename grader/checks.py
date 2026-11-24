"""The scored checks. Each returns (points, max_points, detail)."""
import pathlib

from export import build_holds_report, build_statement
from export.errors import ExportError

from strict_sims import Directory, StrictKestrel, StrictTern

PERIOD = "2026-02"
GOLDEN = pathlib.Path(__file__).parent / "golden"
_WORDS = ["Card purchase", "Payroll deposit", "ATM withdrawal", "Transfer in", "Bill payment, utilities", "Check 2041"]


def money(cents):
    return f"{'-' if cents < 0 else ''}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def kestrel_rows(prefix, count):
    rows = []
    for i in range(count):
        cents = (i * 211 + 475) % 12000 + 50
        word = _WORDS[(i * 5) % len(_WORDS)]
        if word not in ("Payroll deposit", "Transfer in"):
            cents = -cents
        rows.append({"id": f"{prefix}{i:05d}", "posted": f"{PERIOD}-{(i * 7 % 28) + 1:02d}",
                     "description": word, "amount": money(cents), "_cents": cents})
    return rows


def tern_rows(prefix, count, sides=("CREDIT",), statuses=("POSTED",)):
    rows = []
    for i in range(count):
        side = sides[i % len(sides)]
        narrative = (("Payroll deposit", "Transfer in")[i % 2] if side == "CREDIT"
                     else ("Card purchase", "ATM withdrawal", "Bill payment, utilities", "Check 2041")[i % 4])
        rows.append({"posting_id": f"{prefix}{i:05d}", "value_date": f"{PERIOD}-{(i * 11 % 28) + 1:02d}",
                     "amount_minor": 1999 + i * 333, "side": side,
                     "narrative": narrative, "status": statuses[i % len(statuses)]})
    return rows


def expected(member_id, accounts):
    """The statement the runbook describes. accounts: [(account_id, [(date, id, text, cents)])]."""
    import csv, io
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["member", member_id, "period", PERIOD])
    w.writerow(["account", "date", "id", "description", "amount"])
    total = 0
    for account_id, lines in accounts:
        subtotal = 0
        for date, ident, text, cents in sorted(lines):
            w.writerow([account_id, date, ident, text, money(cents)])
            subtotal += cents
        w.writerow(["subtotal", account_id, "", "", money(subtotal)])
        total += subtotal
    w.writerow(["total", "", "", "", money(total)])
    return out.getvalue()


def kestrel_lines(rows):
    return [(r["posted"], r["id"], r["description"], r["_cents"]) for r in rows]


def tern_lines(rows):
    return [(r["value_date"], r["posting_id"], r["narrative"],
             r["amount_minor"] if r["side"] == "CREDIT" else -r["amount_minor"])
            for r in rows if r["status"] == "POSTED" and r["value_date"].startswith(PERIOD)]


def public(rows):
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def run(member_id, directory, kestrel=None, tern=None):
    return build_statement(member_id, PERIOD, directory=directory,
                           kestrel=kestrel or StrictKestrel({}), tern=tern or StrictTern({}))


def compare(got, want, points):
    if got == want:
        return points, points, "statement matches"
    got_l, want_l = got.splitlines(), want.splitlines()
    if len(got_l) != len(want_l):
        return 0, points, f"statement has {len(got_l)} lines, expected {len(want_l)}"
    wrong = sum(1 for a, b in zip(got_l, want_l) if a != b)
    return 0, points, f"{wrong} of {len(want_l)} lines differ from the expected statement"


def check_regression():
    rows = kestrel_rows("KR", 12)
    d = Directory({"2001": ["K-2001-S"]}, {"K-2001-S": "KESTREL"})
    got = run("2001", d, StrictKestrel({"K-2001-S": public(rows)}))
    return compare(got, (GOLDEN / "legacy_2001.csv").read_text(), 10)


def check_kestrel_paging():
    rows = kestrel_rows("KP", 165)
    d = Directory({"2002": ["K-2002-C"]}, {"K-2002-C": "KESTREL"})
    got = run("2002", d, StrictKestrel({"K-2002-C": public(rows)}))
    return compare(got, expected("2002", [("K-2002-C", kestrel_lines(rows))]), 15)


def check_holds_twin():
    holds = [{"id": f"KH{i:05d}", "placed": f"{PERIOD}-{(i * 3 % 28) + 1:02d}",
              "reason": "Check deposit hold" if i % 2 else "Card authorization", "amount": money(2500 + i * 125)}
             for i in range(80)]
    d = Directory({"2010": ["K-2010-C"]}, {"K-2010-C": "KESTREL"})
    got = build_holds_report("2010", directory=d, kestrel=StrictKestrel({"K-2010-C": []}, holds={"K-2010-C": holds}))
    import csv, io
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["account", "placed", "id", "reason", "amount"])
    for h in sorted(holds, key=lambda h: (h["placed"], h["id"])):
        w.writerow(["K-2010-C", h["placed"], h["id"], h["reason"], h["amount"]])
    return compare(got, out.getvalue(), 10)


def check_no_silent_partial():
    # 250 rows: more than the largest page the core allows, so every correct
    # client needs a second call, whatever page size it chose.
    rows = kestrel_rows("KF", 250)
    d = Directory({"2008": ["K-2008-C"]}, {"K-2008-C": "KESTREL"})
    points, notes = 0, []
    cases = [("the core going down mid-list", {"fault_on_call": 2}),
             ("a list that ends early while the core reports more rows", {"cut_short_at": 130})]
    for label, kwargs in cases:
        try:
            run("2008", d, StrictKestrel({"K-2008-C": public(rows)}, **kwargs))
        except ExportError:
            points += 5
            notes.append(f"{label}: ExportError")
        except Exception as e:  # noqa: BLE001
            points += 2.5
            notes.append(f"{label}: raises {type(e).__name__}, not ExportError")
        else:
            notes.append(f"{label}: a statement was still produced")
    return points, 10, "; ".join(notes)


def _tern_case(member, account, rows, points, end_cursor=None, extra=()):
    k_rows = kestrel_rows("KT", 5)
    k_acct = f"K-{member}-S"
    d = Directory({member: [k_acct, account]}, {k_acct: "KESTREL", account: "TERN"})
    got = run(member, d, StrictKestrel({k_acct: public(k_rows)}),
              StrictTern({account: list(rows) + list(extra)}, end_cursor=end_cursor))
    return compare(got, expected(member, [(k_acct, kestrel_lines(k_rows)), (account, tern_lines(rows))]), points)


def check_tern_included():
    outside = [
        {"posting_id": "TX90001", "value_date": "2026-01-31", "amount_minor": 500, "side": "CREDIT", "narrative": "January", "status": "POSTED"},
        {"posting_id": "TX90002", "value_date": "2026-03-01", "amount_minor": 700, "side": "CREDIT", "narrative": "March", "status": "POSTED"},
    ]
    return _tern_case("2003", "T-2003-C", tern_rows("TA", 30), 15, extra=outside)


def check_tern_sign():
    return _tern_case("2004", "T-2004-S", tern_rows("TB", 14, sides=("CREDIT", "DEBIT", "DEBIT")), 10)


def check_tern_status():
    return _tern_case("2005", "T-2005-S", tern_rows("TC", 15, statuses=("POSTED", "PENDING", "POSTED", "REJECTED")), 10)


def check_tern_empty_cursor():
    return _tern_case("2006", "T-2006-C", tern_rows("TD", 30), 5, end_cursor="")


def check_fail_closed():
    cases = [("an account in MIGRATING", "MIGRATING", 4), ("an unrecognized home core", "ARCHIVED", 3),
             ("an account missing from the directory", None, 3)]
    points, notes = 0, []
    for label, core, share in cases:
        bad = "X-2009-S"
        cores = {"K-2009-S": "KESTREL"}
        if core:
            cores[bad] = core
        d = Directory({"2009": ["K-2009-S", bad]}, cores)
        rows = kestrel_rows("KH", 4)
        k = StrictKestrel({"K-2009-S": public(rows), bad: public(kestrel_rows("KX", 3))})
        t = StrictTern({bad: tern_rows("TX", 3)})
        try:
            run("2009", d, k, t)
        except ExportError as e:
            read = any(p.get("account_id") == bad for _, p in k.calls + t.calls)
            named = bad in str(e) or getattr(e, "account_id", None) == bad
            if named and not read:
                points += share
                notes.append(f"{label}: ExportError naming the account")
            else:
                points += share / 2
                notes.append(f"{label}: ExportError, but " + ("the account was read" if read else "the account is not named"))
        except Exception as e:  # noqa: BLE001
            points += share / 2
            notes.append(f"{label}: raises {type(e).__name__}, not ExportError")
        else:
            notes.append(f"{label}: a statement was produced")
    return points, 10, "; ".join(notes)


def check_zero_formatting():
    rows = [
        {"id": "KZ00001", "posted": f"{PERIOD}-03", "description": "Card purchase", "amount": "-0.10", "_cents": -10},
        {"id": "KZ00002", "posted": f"{PERIOD}-04", "description": "Card purchase", "amount": "-0.20", "_cents": -20},
        {"id": "KZ00003", "posted": f"{PERIOD}-05", "description": "Transfer in", "amount": "0.30", "_cents": 30},
    ]
    d = Directory({"2007": ["K-2007-S"]}, {"K-2007-S": "KESTREL"})
    got = run("2007", d, StrictKestrel({"K-2007-S": public(rows)}))
    if "-0.00" in got:
        return 0, 3, "a zero amount is written -0.00"
    return compare(got, expected("2007", [("K-2007-S", kestrel_lines(rows))]), 3)


CHECKS = {
    "regression": ("Existing format unchanged for a legacy-only member", check_regression),
    "kestrel_paging": ("Complete read of a 165-row account against production paging", check_kestrel_paging),
    "holds_twin": ("The same paging fault fixed in the holds report, which the ticket does not mention", check_holds_twin),
    "no_silent_partial": ("A dead core or a short list fails the export instead of shortening it", check_no_silent_partial),
    "tern_included": ("Tern accounts included, period bounds respected", check_tern_included),
    "tern_sign": ("Tern DEBIT and CREDIT shown from the member's point of view", check_tern_sign),
    "tern_status": ("PENDING and REJECTED postings left off", check_tern_status),
    "tern_empty_cursor": ("Empty-string cursor ends the list", check_tern_empty_cursor),
    "fail_closed": ("Unreadable accounts fail the member's export and are never read", check_fail_closed),
    "zero_formatting": ("Zero is written 0.00", check_zero_formatting),
}
