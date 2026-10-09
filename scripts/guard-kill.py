#!/usr/bin/env python3
"""PreToolUse hook for Bash: block pkill/killall, allow kill only with literal PIDs.

Why: on 2026-10-09 an agent ran `pkill -f "start_backend.sh" -P 1`. macOS pkill
stops reading options at the first pattern, so `-P` and `1` became patterns and
SIGTERM hit every process with "1" in its command line, including another
Claude session. A kill by pattern can reach far more than intended; a kill by a
PID that was looked up first cannot.

Allowed:  kill 1234 5678 / kill -9 1234 / kill -s TERM 1234 / kill -0 1234
Blocked:  pkill, killall, kill $pid, kill $(lsof ...), kill %1, kill 0, kill -1,
          xargs kill, and the same inside bash -c / sh -c strings.
"""
import json
import os
import re
import shlex
import sys

SEPARATORS = {";", "&&", "||", "|", "&", "\n", "(", ")", "{", "}", "|&", ";;"}
PREFIXES = {"command", "builtin", "exec", "sudo", "nohup", "env", "time", "nice", "timeout", "then", "do", "else", "!"}
SIGNAL_RE = re.compile(r"^-(\d+|[A-Z][A-Z0-9+-]*|SIG[A-Z0-9+-]+)$", re.I)
PID_RE = re.compile(r"^[1-9]\d*$")

HINT = (
    "Look up the PIDs first (e.g. `lsof -tiTCP:8031 -sTCP:LISTEN`, `pgrep -P 1 -f start_backend.sh`), "
    "show them, then run `kill <pid> <pid>` with the literal numbers."
)


REDIRECT_RE = re.compile(r"(\d*>>?|\d*<|&>>?)(&\d+|&-|\s*[^\s;&|()]+)")


def tokenize(cmd):
    cmd = REDIRECT_RE.sub(" ", cmd.replace("\n", " ; "))
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|(){}")
    lex.whitespace_split = True
    lex.commenters = ""
    return list(lex)


def segments(tokens):
    seg = []
    for tok in tokens:
        if tok in SEPARATORS or set(tok) <= set(";&|(){}"):
            if seg:
                yield seg
            seg = []
        else:
            seg.append(tok)
    if seg:
        yield seg


def strip_prefixes(seg):
    i = 0
    while i < len(seg):
        word = seg[i]
        if word in PREFIXES or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word):
            i += 1
            # skip option-like args of prefixes such as `timeout 10`, `env -i`, `sudo -u x`
            while i < len(seg) and (seg[i].startswith("-") or re.match(r"^\d+[smhd]?$", seg[i])):
                i += 1
            continue
        break
    return seg[i:]


def check_kill_args(args):
    i = 0
    if i < len(args) and args[i] == "-l":
        return None  # list signals, harmless
    if i < len(args) and args[i] in ("-s", "-n"):
        i += 2
    elif i < len(args) and SIGNAL_RE.match(args[i]):
        i += 1
    if i < len(args) and args[i] == "--":
        i += 1
    pids = args[i:]
    if not pids:
        return "kill without a PID"
    bad = [p for p in pids if not PID_RE.match(p)]
    if bad:
        return f"kill with non-literal or unsafe target(s): {' '.join(bad)}"
    return None


def check(cmd, depth=0):
    if depth > 3:
        return None
    try:
        tokens = tokenize(cmd)
    except ValueError:
        if re.search(r"(^|[\s;&|(`$])(pkill|killall)\b", cmd):
            return "pkill/killall is not allowed"
        if re.search(r"(^|[\s;&|(`])kill\s", cmd):
            return "could not parse a command that contains kill"
        return None

    for seg in segments(tokens):
        words = strip_prefixes(seg)
        if not words:
            continue
        name = os.path.basename(words[0])
        if name in ("pkill", "killall"):
            return f"{name} is not allowed (it kills by pattern)"
        if name == "kill":
            reason = check_kill_args(words[1:])
            if reason:
                return reason
        if name == "xargs" and any(os.path.basename(w) in ("kill", "pkill", "killall") for w in words[1:]):
            return "xargs kill is not allowed"
        # nested shells: bash -c "...", sh -c '...', eval "..."
        nested = words[1:] if name == "eval" else [
            words[i + 1] for i in range(len(words) - 1)
            if name in ("bash", "sh", "zsh", "dash") and re.match(r"^-\w*c\w*$", words[i])
        ]
        for w in nested:
            reason = check(w, depth + 1)
            if reason:
                return reason
    # command substitution inside a word, e.g. $(pkill ...) or `kill ...`
    for inner in re.findall(r"\$\(([^()]*)\)|`([^`]*)`", cmd):
        text = inner[0] or inner[1]
        if re.search(r"\b(pkill|killall|kill)\b", text):
            reason = check(text, depth + 1)
            if reason:
                return reason
    return None


HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def strip_heredocs(cmd):
    """Drop heredoc bodies: they are data (commit messages, files), not commands."""
    out, lines, i = [], cmd.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        for m in HEREDOC_RE.finditer(line):
            end = m.group(2)
            while i < len(lines) and lines[i].strip() != end:
                i += 1
            i += 1
    return "\n".join(out)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    cmd = strip_heredocs((data.get("tool_input") or {}).get("command") or "")
    if not re.search(r"\b(pkill|killall|kill)\b", cmd):
        return 0
    reason = check(cmd)
    if not reason:
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"guard-kill: {reason}. Only `kill <literal PID>...` is allowed. {HINT}",
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
