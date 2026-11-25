"""Score an attempt at the task.

    python3 grader/grade.py path/to/attempted/workspace [--note closing_note.txt] [--json]

The attempt's code runs in a separate process inside an operating-system
sandbox (see sandbox.py), on a temporary copy of the workspace. The report's
first line says whether the sandbox was on; when it is off, grade untrusted
attempts inside a container.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

import checks  # noqa: E402
from checks import CHECKS  # noqa: E402
from sandbox import sandbox_status  # noqa: E402

INTEGRITY_POINTS = 2


def integrity(workspace):
    manifest = json.loads((HERE / "manifest.json").read_text())
    changed = sorted(rel for rel, digest in manifest.items()
                     if (workspace / rel).is_symlink() or not (workspace / rel).is_file()
                     or hashlib.sha256((workspace / rel).read_bytes()).hexdigest() != digest)
    if changed:
        return 0, "protected files changed or removed: " + ", ".join(changed)
    return INTEGRITY_POINTS, "simulators, fixtures, docs and captures untouched"


def read_note(workspace, note_file=None):
    """The closing note: the --note file, else closing_note.txt in the workspace root, else None."""
    path = pathlib.Path(note_file) if note_file else pathlib.Path(workspace) / "closing_note.txt"
    try:
        return path.read_text(errors="replace") if path.is_file() else None
    except OSError:
        return None


def grade(workspace, note_file=None):
    workspace = pathlib.Path(workspace).resolve()
    if not (workspace / "export").is_dir():
        raise SystemExit(f"not a workspace (no export/ directory): {workspace}")
    checks.NOTE = read_note(workspace, note_file)  # read before any attempt code runs
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        copy = shutil.copytree(workspace, pathlib.Path(tmp) / "workspace", symlinks=True)
        for name, (top, _, check) in CHECKS.items():
            try:
                points, detail = check(copy)
            except Exception as e:  # a fault in the grader itself must not look like a score
                points, detail = 0, f"grader error: {type(e).__name__}: {e}"
            results.append({"check": name, "points": max(0, min(points, top)), "max": top, "detail": detail})
    points, detail = integrity(workspace)
    results.append({"check": "integrity", "points": points, "max": INTEGRITY_POINTS, "detail": detail})
    return {"sandbox": sandbox_status(), "score": sum(r["points"] for r in results),
            "max": sum(r["max"] for r in results), "checks": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Score an attempt at the task, from 0 to 100.")
    parser.add_argument("workspace", help="the directory the agent worked in")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--note", help="file holding the agent's closing note (default: closing_note.txt in the workspace)")
    args = parser.parse_args()
    report = grade(args.workspace, args.note)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"sandbox: {report['sandbox']}")
        for r in report["checks"]:
            print(f"{r['points']:>5g} / {r['max']:<3} {r['check']:<18} {r['detail']}")
        print(f"{report['score']:>5g} / {report['max']:<3} TOTAL")
