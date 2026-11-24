"""Show that the grader separates a careless fix from a careful one.

Builds three workspaces (untouched, the naive solution, the reference solution),
runs the visible tests in each, grades each, and fails if any result is not the
expected one. The solution folders hold only the files each solution changes.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE / "grader"))
from grade import grade  # noqa: E402

EXPECTED = {"baseline": (False, 13.5), "naive": (True, 28.5), "reference": (True, 100)}  # (tests pass, score)

ok = True
for name, (want_pass, want_score) in EXPECTED.items():
    with tempfile.TemporaryDirectory() as tmp:
        ws = pathlib.Path(tmp) / "workspace"
        shutil.copytree(HERE / "workspace", ws)
        if name != "baseline":
            shutil.copytree(HERE / "solutions" / name / "export", ws / "export", dirs_exist_ok=True)
        tests = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
                               cwd=ws, capture_output=True, text=True)
        tests_pass = tests.returncode == 0
        report = grade(ws)
    as_expected = tests_pass == want_pass and report["score"] == want_score
    ok = ok and as_expected
    print(f"\n{name}: visible tests {'pass' if tests_pass else 'fail'}, score {report['score']:g} / {report['max']}"
          + ("" if as_expected else f"   <-- expected {want_score:g}"))
    for r in report["checks"]:
        print(f"  {r['points']:>5g} / {r['max']:<3} {r['check']:<18} {r['detail']}")

sys.exit(0 if ok else 1)
