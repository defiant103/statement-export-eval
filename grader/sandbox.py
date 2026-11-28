"""Runs an attempt's code in a process of its own, inside an operating-system sandbox.

The attempt never shares a process with the grader. It gets proxy objects for
the directory and the two cores; every call it makes crosses a pipe to this
side, where the grader's transports answer it. The attempt therefore cannot
import, patch or inspect anything the grader uses to judge it, and cannot reach
past the API into a transport's data.

The process also runs inside a sandbox: sandbox-exec on macOS, bwrap on Linux.
It has no network, cannot start other processes (on Linux, none can outlive
it), can read only the workspace copy, its own scratch folder and the system
and Python install paths, and can write only to its scratch folder. It starts
with an environment holding only a minimal PATH and HOME and TMPDIR set to its
scratch folder, under limits on CPU time, file size, open files and (where the
system enforces it) memory, and its whole process group is killed when it is
done or out of time. When neither tool works, the
process runs without one and the report says so.
"""
import functools
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass

from strict_sims import Fault

TIME_LIMIT = 10  # seconds for one call into the attempt
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
SYSTEM_PATHS = ("/usr", "/bin", "/lib", "/lib64", "/etc/ld.so.cache", "/System", "/dev")  # missing ones are skipped

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
                                      jedha=_Transport("jedha"), scarif=_Transport("scarif"))
    else:
        text = export.build_holds_report(spec["member_id"], directory=_Directory(), jedha=_Transport("jedha"))
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


# ---- the sandbox ----

def _install_paths():
    """The system and Python install paths, which every child may read."""
    executable = (os.path.dirname(sys.executable), os.path.dirname(os.path.realpath(sys.executable)))
    python = sorted({os.path.realpath(p) for p in (sys.prefix, sys.base_prefix, *executable)})
    return [p for p in SYSTEM_PATHS if os.path.exists(p)] + python


def _sandbox_exec(workspace, scratch):
    # Everything is allowed except what is denied here. Reading a path's metadata
    # stays allowed, because Python resolves its own location at startup.
    readable = " ".join(f"(subpath {json.dumps(p)})" for p in _install_paths() + [workspace, scratch])
    profile = f'''(version 1)
        (allow default)
        (deny network*)
        (deny process-fork)
        (deny file-read*)
        (allow file-read-metadata)
        (allow file-read* (literal "/") {readable})
        (deny file-write*)
        (allow file-write* (subpath {json.dumps(scratch)}) (literal "/dev/null"))'''
    return [SANDBOX_EXEC, "-p", profile]


def _bwrap(workspace, scratch):
    # New namespaces: no network, and a process namespace that ends with the child.
    command = [shutil.which("bwrap"), "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
               "--dev", "/dev", "--tmpfs", "/tmp"]
    for path in _install_paths():
        if path != "/dev":
            command += ["--ro-bind", path, path]
    return command + ["--ro-bind", workspace, workspace, "--bind", scratch, scratch, "--chdir", scratch]


def _wrapper(workspace, scratch):
    if sys.platform == "darwin" and os.access(SANDBOX_EXEC, os.X_OK):
        return _sandbox_exec(workspace, scratch)
    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        return _bwrap(workspace, scratch)
    return []


LIMITS = {"RLIMIT_CPU": 60, "RLIMIT_FSIZE": 64 * 2**20, "RLIMIT_NOFILE": 256, "RLIMIT_AS": 2 * 2**30}


def _limit_resources():
    """Runs in the child before it starts: caps what one attempt process can use."""
    for name, value in LIMITS.items():
        try:
            resource.setrlimit(getattr(resource, name), (value, value))
        except (ValueError, OSError):
            pass  # macOS does not enforce RLIMIT_AS; the time limit still applies


def _start(workspace, scratch, code, *args, sandboxed):
    """Start Python on `code` with a clean environment, in a session of its own."""
    command = [sys.executable, "-I", "-B", "-c", code, *args]
    if sandboxed:
        command = _wrapper(workspace, scratch) + command
    return subprocess.Popen(command, cwd=scratch, env={"PATH": "/usr/bin:/bin", "HOME": scratch, "TMPDIR": scratch},
                            text=True, errors="replace", stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, start_new_session=True, preexec_fn=_limit_resources)


@functools.cache
def sandbox_on():
    """True when the sandbox works here: a child inside it must fail to read this file."""
    with tempfile.TemporaryDirectory() as tmp:
        scratch = os.path.realpath(tmp)
        if not _wrapper(scratch, scratch):
            return False
        probe = "import sys\ntry:\n    open(sys.argv[1]).read()\nexcept OSError:\n    print('denied')"
        proc = _start(scratch, scratch, probe, os.path.realpath(__file__), sandboxed=True)
        try:
            out, _ = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            _kill(proc)
            return False
        return out.strip() == "denied"


def sandbox_status():
    return "on" if sandbox_on() else "off (run inside a container)"


def _kill(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    proc.kill()
    proc.wait()


# ---- calling the attempt ----

@dataclass
class Result:
    text: str | None = None       # what the entry point returned
    error: str | None = None      # "ExportError", another exception's name, "Timeout" or "Crashed"
    message: str = ""
    account_id: str | None = None

    def names(self, account_id):
        return account_id in self.message or self.account_id == account_id


def invoke(workspace, entry, member_id, *, directory, jedha, scarif=None, period=None):
    """Call the attempt's entry point ("statement" or "holds") and return a Result."""
    workspace = os.path.realpath(workspace)
    spec = {"workspace": workspace, "entry": entry, "member_id": member_id, "period": period}
    with tempfile.TemporaryDirectory() as tmp:
        scratch = os.path.realpath(tmp)
        proc = _start(workspace, scratch, _DRIVER, sandboxed=sandbox_on())
        timed_out = threading.Event()

        def stop():
            timed_out.set()
            _kill(proc)

        timer = threading.Timer(TIME_LIMIT, stop)
        timer.start()
        try:
            _send(proc, spec)
            for line in proc.stdout:
                message = json.loads(line)
                if "done" in message:
                    return _result(message["done"])
                _send(proc, _answer(message, directory, jedha, scarif))
            return Result(error="Timeout" if timed_out.is_set() else "Crashed")
        except (ValueError, KeyError, TypeError, AttributeError, OSError):
            return Result(error="Timeout" if timed_out.is_set() else "Crashed",
                          message="unreadable reply from the attempt")
        finally:
            timer.cancel()
            _kill(proc)


def _send(proc, message):
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def _answer(message, directory, jedha, scarif):
    try:
        if message["call"] == "accounts_for":
            return {"ok": directory.accounts_for(message["key"])}
        if message["call"] == "home_core":
            return {"ok": directory.home_core(message["key"])}
        core = {"jedha": jedha, "scarif": scarif}[message["call"]]
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
