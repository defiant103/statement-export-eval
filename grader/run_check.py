"""Run one check against one workspace and print its result as JSON. Run with python3 -I."""
import json
import pathlib
import sys

workspace, name = sys.argv[1], sys.argv[2]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, workspace)

import checks  # noqa: E402

try:
    points, top, detail = checks.CHECKS[name][1]()
except Exception as e:  # noqa: BLE001
    points, top, detail = 0, None, f"raised {type(e).__name__}: {e}"
print(json.dumps({"points": points, "max": top, "detail": detail}))
