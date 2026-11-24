"""Runs an attempt's code in a process of its own.

The attempt never shares a process with the grader. It gets proxy objects for
the directory and the two cores; every call it makes crosses a pipe to this
side, where the grader's transports answer it. The attempt therefore cannot
import, patch or inspect anything the grader uses to judge it, and cannot reach
past the API into a transport's data.
"""
import json
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass

from strict_sims import Fault

TIME_LIMIT = 10  # seconds for one call into the attempt

# Runs inside the attempt's process. It takes what it needs from the standard
# library before the workspace goes on the path, and moves the attempt's stdout
# out of the way of the protocol stream.
_DRIVER = r'''
import json, sys
_in, _out = sys.stdin, sys.stdout
sys.stdout = sys.stderr
_loads, _dumps = json.loads, json.dumps
spec = _loads(_in.readline())
sys.path.insert(0, spec["workspace"])


def _ask(message):
    _out.write(_dumps(message) + "\n")
    _out.flush()
    return _loads(_in.readline())


class _Transport:
    def __init__(self, core):
        self._core = core

    def call(self, op, params):
        reply = _ask({"call": self._core, "op": op, "params": params})
        if "fault" in reply:
            from export.errors import TransportError
            raise TransportError(*reply["fault"])
        return reply["ok"]


class _Directory:
    def accounts_for(self, member_id):
        return self._lookup("accounts_for", member_id)

    def home_core(self, account_id):
        return self._lookup("home_core", account_id)

    def _lookup(self, what, key):
        reply = _ask({"call": what, "key": key})
        if "missing" in reply:
            raise KeyError(key)
        return reply["ok"]


try:
    import export
    if spec["entry"] == "statement":
        text = export.build_statement(spec["member_id"], spec["period"], directory=_Directory(),
                                      kestrel=_Transport("kestrel"), tern=_Transport("tern"))
    else:
        text = export.build_holds_report(spec["member_id"], directory=_Directory(), kestrel=_Transport("kestrel"))
    done = {"text": text}
except BaseException as e:
    kind = type(e).__name__
    try:
        from export.errors import ExportError
        if ExportError is not Exception and isinstance(e, ExportError):
            kind = "ExportError"
    except Exception:
        pass
    done = {"error": kind, "message": str(e), "account_id": getattr(e, "account_id", None)}
_out.write(_dumps({"done": done}) + "\n")
_out.flush()
'''


@dataclass
class Result:
    text: str | None = None       # what the entry point returned
    error: str | None = None      # "ExportError", another exception's name, "Timeout" or "Crashed"
    message: str = ""
    account_id: str | None = None

    def names(self, account_id):
        return account_id in self.message or self.account_id == account_id


def invoke(workspace, entry, member_id, *, directory, kestrel, tern=None, period=None):
    """Call the attempt's entry point ("statement" or "holds") and return a Result."""
    spec = {"workspace": str(workspace), "entry": entry, "member_id": member_id, "period": period}
    with tempfile.TemporaryDirectory() as scratch:
        proc = subprocess.Popen([sys.executable, "-I", "-c", _DRIVER], cwd=scratch, text=True, errors="replace",
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        timed_out = threading.Event()

        def stop():
            timed_out.set()
            proc.kill()

        timer = threading.Timer(TIME_LIMIT, stop)
        timer.start()
        try:
            _send(proc, spec)
            for line in proc.stdout:
                message = json.loads(line)
                if "done" in message:
                    return _result(message["done"])
                _send(proc, _answer(message, directory, kestrel, tern))
            return Result(error="Timeout" if timed_out.is_set() else "Crashed")
        except (ValueError, KeyError, TypeError, AttributeError, OSError):
            return Result(error="Timeout" if timed_out.is_set() else "Crashed",
                          message="unreadable reply from the attempt")
        finally:
            timer.cancel()
            proc.kill()
            proc.wait()


def _send(proc, message):
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def _answer(message, directory, kestrel, tern):
    try:
        if message["call"] == "accounts_for":
            return {"ok": directory.accounts_for(message["key"])}
        if message["call"] == "home_core":
            return {"ok": directory.home_core(message["key"])}
        core = {"kestrel": kestrel, "tern": tern}[message["call"]]
        return {"ok": core.call(message["op"], message["params"])}
    except Fault as fault:
        return {"fault": [fault.status, fault.body]}
    except KeyError:
        return {"missing": True}


def _result(done):
    if "error" in done:
        account_id = done.get("account_id")
        return Result(error=str(done["error"]), message=str(done.get("message", "")),
                      account_id=account_id if isinstance(account_id, str) else None)
    text = done.get("text")
    if not isinstance(text, str):
        return Result(error="Crashed", message="the entry point did not return text")
    return Result(text=text)
