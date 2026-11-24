"""Score an attempt at the task.

    python3 grader/grade.py path/to/attempted/workspace [--json]

Each check runs in its own Python process with a time limit, against the
grader's own production-faithful transports. The attempt's code is executed, so
run this inside a sandbox when the attempt is untrusted.
"""
import hashlib
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
MAX = {"regression": 10, "kestrel_paging": 15, "holds_twin": 10, "no_silent_partial": 10, "tern_included": 15,
       "tern_sign": 10, "tern_status": 10, "tern_empty_cursor": 5, "fail_closed": 10, "zero_formatting": 3}
TIME_LIMIT = 20


def integrity(workspace):
    manifest = json.loads((HERE / "manifest.json").read_text())
    changed = [rel for rel, digest in manifest.items()
               if not (workspace / rel).is_file()
               or hashlib.sha256((workspace / rel).read_bytes()).hexdigest() != digest]
    if changed:
        return 0, 2, "protected files changed or removed: " + ", ".join(sorted(changed))
    return 2, 2, "simulators, fixtures and golden file untouched"


def grade(workspace):
    sys.path.insert(0, str(HERE))
    workspace = pathlib.Path(workspace).resolve()
    results = []
    for name, top in MAX.items():
        try:
            proc = subprocess.run([sys.executable, "-I", str(HERE / "run_check.py"), str(workspace), name],
                                  capture_output=True, text=True, timeout=TIME_LIMIT)
            out = json.loads(proc.stdout.strip().splitlines()[-1])
            points, detail = out["points"], out["detail"]
        except subprocess.TimeoutExpired:
            points, detail = 0, f"did not finish within {TIME_LIMIT}s"
        except Exception:  # noqa: BLE001
            points, detail = 0, "check could not run: " + (proc.stderr.strip().splitlines() or ["no output"])[-1]
        results.append({"check": name, "points": points, "max": top, "detail": detail})
    points, top, detail = integrity(workspace)
    results.append({"check": "integrity", "points": points, "max": top, "detail": detail})
    return {"score": sum(r["points"] for r in results), "max": sum(r["max"] for r in results), "checks": results}


if __name__ == "__main__":
    report = grade(sys.argv[1])
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        for r in report["checks"]:
            print(f"{r['points']:>5g} / {r['max']:<3} {r['check']:<18} {r['detail']}")
        print(f"{report['score']:>5g} / {report['max']:<3} TOTAL")
