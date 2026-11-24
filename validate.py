"""Show that the grader separates a careless fix from a careful one.

Builds three workspaces (untouched, the naive solution, the reference solution),
runs the visible tests in each and grades each.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE / "grader"))
from grade import grade  # noqa: E402

for name in ("baseline", "naive", "reference"):
    with tempfile.TemporaryDirectory() as tmp:
        ws = pathlib.Path(tmp) / "workspace"
        shutil.copytree(HERE / "workspace", ws)
        if name != "baseline":
            shutil.copytree(HERE / "solutions" / name / "export", ws / "export", dirs_exist_ok=True)
        tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                               cwd=ws, capture_output=True, text=True)
        report = grade(ws)
        print(f"\n{name}: visible tests {'pass' if tests.returncode == 0 else 'FAIL'}, score {report['score']:g} / {report['max']}")
        for r in report["checks"]:
            print(f"  {r['points']:>5g} / {r['max']:<3} {r['check']:<18} {r['detail']}")
