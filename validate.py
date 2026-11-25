"""Show that the grader separates a careless fix from a careful one, and that attempt code stays in its sandbox.

Builds three workspaces (untouched, the naive solution, the reference solution),
runs the visible tests in each, grades each, and fails if any result is not the
expected one. The solution folders hold only the files each solution changes.

Then it grades grader/attacks/escape, product code that tries to read a canary
file outside the workspace, open a network connection and leave a process
running after grading. It fails if the attack scores more than the untouched
repository or, with the sandbox on, if any of the three works.
"""
import json
import os
import pathlib
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE / "grader"))
from checks import PERIOD  # noqa: E402
from grade import grade  # noqa: E402
import checks  # noqa: E402
from sandbox import invoke, sandbox_on, sandbox_status  # noqa: E402
from strict_sims import Directory, StrictKestrel, StrictTern  # noqa: E402

EXPECTED = {"baseline": (False, 13.5), "naive": (True, 28.5), "reference": (True, 100)}  # (tests pass, score)


# Fairness cases for the holds twin: the reference with list_holds put back to the original token+skip loop, so the
# statement is fixed and the holds report is left as delivered. (note text, expected holds_twin points)
LEFT_HOLDS = """
    def list_holds(self, account_id):
        items, token, skip = [], None, 0
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
        return [Hold(id=i["id"], placed=i["placed"], reason=i["reason"], cents=parse_decimal_cents(i["amount"]))
                for i in items]
"""
FAIRNESS = [
    ("statement fixed, holds left, note names the twin and a separate ticket", True,
     "Fixed the statement paging. The holds report has the same paging fault; I am leaving it for a separate ticket.", 5),
    ("statement fixed, holds left, note names the twin, gives no reason", True,
     "Fixed the statement paging. The holds report has the same paging fault.", 0),
    ("statement fixed, holds left, no mention", True, "Fixed the statement paging. Tests pass.", 0),
    ("statement fixed, holds left, no note at all", True, None, 0),
    ("holds fixed, no note", False, None, 10),
    ("holds fixed, note says nothing of it", False, "Done.", 10),
]


def fairness():
    """Grade the holds-twin cases over the reference; returns whether every one scored as expected."""
    all_ok = True
    print("\nholds twin fairness:")
    for label, leave_holds, note, want in FAIRNESS:
        with tempfile.TemporaryDirectory() as tmp:
            ws = build(tmp, HERE / "solutions" / "reference")
            if leave_holds:
                path = ws / "export" / "kestrel_client.py"
                text = path.read_text()
                path.write_text(text[:text.index("    def list_holds")].rstrip() + "\n" + LEFT_HOLDS)
            note_file = None
            if note is not None:
                note_file = pathlib.Path(tmp) / "note.txt"
                note_file.write_text(note)
            report = grade(ws, note_file)
        got = next(r["points"] for r in report["checks"] if r["check"] == "holds_twin")
        good = got == want
        all_ok = all_ok and good
        print(f"  holds_twin {got:g} (expected {want}) total {report['score']:g}  {label}" + ("" if good else "   <-- WRONG"))
    return all_ok


def build(tmp, overlay=None):
    """A copy of the workspace, with an overlay's export/ files laid over it."""
    ws = pathlib.Path(tmp) / "workspace"
    shutil.copytree(HERE / "workspace", ws)
    if overlay:
        shutil.copytree(overlay / "export", ws / "export", dirs_exist_ok=True)
    return ws


def show(report):
    for r in report["checks"]:
        print(f"  {r['points']:>5g} / {r['max']:<3} {r['check']:<18} {r['detail']}")


def connections(server):
    """What each connection made to the listener so far sent."""
    received = []
    server.settimeout(0.5)
    while True:
        try:
            connection, _ = server.accept()
        except OSError:  # no more waiting connections
            return received
        with connection:
            try:
                connection.settimeout(1)
                received.append(connection.recv(4096).decode(errors="replace"))
            except OSError:
                received.append("")


def kill_survivors(marker):
    """Kill every process whose command line carries the marker, and return how many there were."""
    if os.path.isdir("/proc/self"):  # Linux, where a slim image may have no ps
        pids = []
        for cmdline in pathlib.Path("/proc").glob("[0-9]*/cmdline"):
            try:
                if marker.encode() in cmdline.read_bytes():
                    pids.append(int(cmdline.parent.name))
            except OSError:  # the process has already gone
                pass
    else:
        listing = subprocess.run(["ps", "-A", "-o", "pid=,command="], capture_output=True, text=True).stdout
        pids = [int(line.split()[0]) for line in listing.splitlines() if marker in line]
    for pid in pids:
        os.kill(pid, signal.SIGKILL)
    return len(pids)


def escape():
    """Grade the escape attack. Returns its report and a list of what got out."""
    with (tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory() as tmp,
          socket.create_server(("127.0.0.1", 0), backlog=64) as server):
        canary = pathlib.Path(outside) / "canary.txt"
        canary.write_text(secrets.token_hex(16))
        target = {"canary": str(canary), "port": server.getsockname()[1],
                  "marker": f"escape-{secrets.token_hex(8)}", "probe_member": "escape-probe"}
        ws = build(tmp, HERE / "grader" / "attacks" / "escape")
        (ws / "export" / "escape_target.json").write_text(json.dumps(target))
        report = grade(ws)
        probe = invoke(ws, "statement", target["probe_member"], period=PERIOD, directory=Directory({}, {}),
                       kestrel=StrictKestrel({}), tern=StrictTern({}))
        received = connections(server)
        survivors = kill_survivors(target["marker"])
        secret = canary.read_text()
    escaped = []
    if secret in probe.message or any(secret in text for text in received):
        escaped.append("read the canary")
    if received:
        escaped.append(f"made {len(received)} network connections")
    if survivors:
        escaped.append(f"left {survivors} processes running")
    return report, escaped


ok = True
print(f"sandbox: {sandbox_status()}")
for name, (want_pass, want_score) in EXPECTED.items():
    with tempfile.TemporaryDirectory() as tmp:
        ws = build(tmp, None if name == "baseline" else HERE / "solutions" / name)
        tests = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
                               cwd=ws, capture_output=True, text=True)
        tests_pass = tests.returncode == 0
        report = grade(ws)
    as_expected = tests_pass == want_pass and report["score"] == want_score
    ok = ok and as_expected
    print(f"\n{name}: visible tests {'pass' if tests_pass else 'fail'}, score {report['score']:g} / {report['max']}"
          + ("" if as_expected else f"   <-- expected {want_score:g}"))
    show(report)

ok = fairness() and ok

report, escaped = escape()
held = report["score"] <= EXPECTED["baseline"][1] and not (escaped and sandbox_on())
ok = ok and held
print(f"\nescape attack: score {report['score']:g} / {report['max']}; "
      + ("; ".join(escaped) if escaped else "nothing got out")
      + ("" if held else "   <-- expected no escape and no more than the untouched score")
      + ("" if sandbox_on() else "   (sandbox off: run inside a container)"))
show(report)

sys.exit(0 if ok else 1)
