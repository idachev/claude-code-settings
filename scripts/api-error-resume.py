#!/usr/bin/env python3
"""StopFailure hook: resume a session that stopped on an API error.

Usage (settings.json, hook event StopFailure, matcher "server_error|unknown|overloaded"):
    python3 ~/.claude/scripts/api-error-resume.py

The hook returns at once. A detached waiter waits until api.anthropic.com
answers again, checks that the session is still stuck on the same error, and
then starts a short headless `claude -p` that sends the stuck session a
cross-session message asking it to continue. An idle session starts a new turn
when such a message arrives.

The waiter skips the send when the session is gone, busy, or already moved past
the error (the user typed something). One waiter per session at a time; at most
MAX_ATTEMPTS sends per session, with a growing delay between them.

Log: ~/.claude/logs/api-error-resume.log. State: ~/.claude/state/api-error-resume/.
Env overrides (for tests): API_RESUME_POLL, API_RESUME_BASE_DELAY, API_RESUME_MODEL.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

GUARD_ENV = "API_ERROR_RESUME_SENDER"   # set for the sender, so it never triggers itself
HOME = Path.home() / ".claude"
LOG = HOME / "logs" / "api-error-resume.log"
STATE = HOME / "state" / "api-error-resume"
CHECK_URL = "https://api.anthropic.com/"
POLL = int(os.environ.get("API_RESUME_POLL", "15"))
BASE_DELAY = int(os.environ.get("API_RESUME_BASE_DELAY", "20"))
MODEL = os.environ.get("API_RESUME_MODEL", "haiku")
MAX_WAIT = 6 * 3600          # give up waiting for the network after this
MAX_ATTEMPTS = 5             # sends per session before giving up
ATTEMPT_RESET = 3600         # a quiet hour resets the attempt counter
SENDER_TIMEOUT = 180


def log(sid, msg):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} pid={os.getpid()} sid={sid[:8]} {msg}", flush=True)


def detach():
    """Fork twice so the hook returns now and the waiter outlives it."""
    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    devnull = os.open(os.devnull, os.O_RDONLY)
    out = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(devnull, 0)
    os.dup2(out, 1)
    os.dup2(out, 2)


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def take_lock(sid):
    """One waiter per session. A lock whose owner is dead is taken over."""
    lock = STATE / f"{sid}.lock"
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return lock
        except FileExistsError:
            try:
                owner = int(lock.read_text().strip() or "0")
            except (OSError, ValueError):
                owner = 0
            if owner and pid_alive(owner):
                return None
            lock.unlink(missing_ok=True)
    return None


def load_attempts(sid):
    path = STATE / f"{sid}.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {}
    if time.time() - data.get("last", 0) > ATTEMPT_RESET:
        data = {"count": 0, "last": 0}
    return path, data


def network_up():
    """Any HTTP answer from the API host means the network is back."""
    try:
        urllib.request.urlopen(CHECK_URL, timeout=8)
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError):
        return False
    return True


def still_stuck(transcript):
    """True when the last user/assistant entry is still the API error message."""
    try:
        with open(transcript, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 262144))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return False
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") in ("user", "assistant"):
            return bool(entry.get("isApiErrorMessage"))
    return False


def find_session(claude, sid):
    """Return (name, status) of the live session, or (None, reason)."""
    try:
        out = subprocess.run([claude, "agents", "--json"], capture_output=True,
                             text=True, timeout=30).stdout
        rows = json.loads(out)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        return None, f"claude agents failed: {e}"
    match = [r for r in rows if r.get("sessionId") == sid]
    if not match:
        return None, "session not running"
    name = match[0].get("name") or ""
    if not name:
        return None, "session has no name"
    if sum(1 for r in rows if r.get("name") == name) > 1:
        return None, f"name {name!r} is not unique"
    return name, match[0].get("status", "")


def send(claude, name, error):
    message = (f"Network is back. Your last turn stopped on an API error ({error}). "
               "Continue the user's interrupted task from where it stopped. "
               "(Sent automatically by ~/.claude/scripts/api-error-resume.py.)")
    prompt = ("Use ToolSearch with query 'select:SendMessage' to load the SendMessage tool. "
              f"Then call SendMessage with to={json.dumps(name)} and this exact message:\n"
              f"{message}\nDo nothing else. Print the tool result.")
    env = dict(os.environ, **{GUARD_ENV: "1"})
    result = subprocess.run(
        [claude, "-p", "--model", MODEL,
         "--settings", '{"disableAllHooks": true}',
         "--allowedTools", "SendMessage,ToolSearch,ListAgents"],
        input=prompt, capture_output=True, text=True, env=env, timeout=SENDER_TIMEOUT)
    return result.returncode, (result.stdout + result.stderr).strip()[-600:]


def wait_and_resume(sid, transcript, error):
    STATE.mkdir(parents=True, exist_ok=True)
    lock = take_lock(sid)
    if lock is None:
        log(sid, "another waiter already runs for this session")
        return
    try:
        path, attempts = load_attempts(sid)
        if attempts["count"] >= MAX_ATTEMPTS:
            log(sid, f"gave up: {MAX_ATTEMPTS} sends in the last hour")
            return
        delay = BASE_DELAY * (2 ** attempts["count"])
        log(sid, f"error={error} attempt={attempts['count'] + 1} waiting {delay}s, then for the network")
        time.sleep(delay)
        deadline = time.time() + MAX_WAIT
        while not network_up():
            if time.time() > deadline:
                log(sid, "gave up: network still down")
                return
            time.sleep(POLL)
        time.sleep(5)   # let DNS and the session settle
        if not still_stuck(transcript):
            log(sid, "session already moved past the error, nothing to do")
            return
        claude = shutil.which("claude")
        if not claude:
            log(sid, "claude not on PATH")
            return
        name, status = find_session(claude, sid)
        if name is None:
            log(sid, f"skip: {status}")
            return
        if status != "idle":
            log(sid, f"skip: session {name!r} is {status}")
            return
        attempts = {"count": attempts["count"] + 1, "last": time.time()}
        path.write_text(json.dumps(attempts))
        code, out = send(claude, name, error)
        log(sid, f"sent continue to {name!r} exit={code} out={out!r}")
    finally:
        lock.unlink(missing_ok=True)


def main():
    if os.environ.get(GUARD_ENV):
        return
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    sid = payload.get("session_id") or ""
    transcript = payload.get("transcript_path") or ""
    if not sid or not transcript:
        return
    detach()
    try:
        wait_and_resume(sid, transcript, payload.get("error", "unknown"))
    except Exception as e:  # the waiter has no caller to report to
        log(sid, f"crashed: {e!r}")


if __name__ == "__main__":
    main()
