"""Score an attempt at the task.

    python3 grader/grade.py path/to/attempted/workspace [--json]

The attempt's code runs in a separate process (see sandbox.py), on a temporary
copy of the workspace. It is still arbitrary code with the same file and
network access as this script, so grade untrusted attempts inside a sandbox.
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

from checks import CHECKS  # noqa: E402

INTEGRITY_POINTS = 2


def integrity(workspace):
    manifest = json.loads((HERE / "manifest.json").read_text())
    changed = sorted(rel for rel, digest in manifest.items()
                     if not (workspace / rel).is_file()
                     or hashlib.sha256((workspace / rel).read_bytes()).hexdigest() != digest)
    if changed:
        return 0, "protected files changed or removed: " + ", ".join(changed)
    return INTEGRITY_POINTS, "simulators, fixtures, docs and captures untouched"


def grade(workspace):
    workspace = pathlib.Path(workspace).resolve()
    if not (workspace / "export").is_dir():
        raise SystemExit(f"not a workspace (no export/ directory): {workspace}")
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        copy = shutil.copytree(workspace, pathlib.Path(tmp) / "workspace")
        for name, (top, _, check) in CHECKS.items():
            try:
                points, detail = check(copy)
            except Exception as e:  # a fault in the grader itself must not look like a score
                points, detail = 0, f"grader error: {type(e).__name__}: {e}"
            results.append({"check": name, "points": max(0, min(points, top)), "max": top, "detail": detail})
    points, detail = integrity(workspace)
    results.append({"check": "integrity", "points": points, "max": INTEGRITY_POINTS, "detail": detail})
    return {"score": sum(r["points"] for r in results), "max": sum(r["max"] for r in results), "checks": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Score an attempt at the task, from 0 to 100.")
    parser.add_argument("workspace", help="the directory the agent worked in")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args()
    report = grade(args.workspace)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for r in report["checks"]:
            print(f"{r['points']:>5g} / {r['max']:<3} {r['check']:<18} {r['detail']}")
        print(f"{report['score']:>5g} / {report['max']:<3} TOTAL")
