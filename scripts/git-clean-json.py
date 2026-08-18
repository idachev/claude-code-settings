#!/usr/bin/env python3
"""Git clean filter: strip machine-local / company-derived keys before staging.

Claude Code rewrites ~/.claude/settings.json and ~/.claude/.claude.json at runtime,
injecting state derived from whatever repo happened to be open. Because this repo is
public, that state must never reach the index. This filter runs on `git add`/`git diff`
(worktree -> index) only; the working files keep everything.

Usage (from .gitattributes + .git/config):  git-clean-json.py <settings|claude-json>

Fails open: if stdin is not parseable JSON, it is passed through byte-for-byte
rather than risking a corrupted commit.
"""
import collections
import json
import sys

# settings.json: Claude Code's auto-mode "environment" learning writes an inventory of
# the current org's cloud infra (registries, buckets, namespaces, CI secret names).
SETTINGS_DROP = ("autoMode",)

# .claude.json: keep only the hand-written MCP server declarations. Everything else is
# machine/user identifiers and a growing map of every local project path.
CLAUDE_JSON_KEEP = ("mcpServers",)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    raw = sys.stdin.buffer.read()

    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=collections.OrderedDict)
    except (UnicodeDecodeError, json.JSONDecodeError):
        sys.stdout.buffer.write(raw)
        return 0

    if mode == "settings":
        for key in SETTINGS_DROP:
            data.pop(key, None)
    elif mode == "claude-json":
        data = collections.OrderedDict(
            (k, v) for k, v in data.items() if k in CLAUDE_JSON_KEEP
        )
    else:
        sys.stdout.buffer.write(raw)
        return 0

    out = json.dumps(data, indent=2, ensure_ascii=False)
    # Match the source file's trailing-newline convention to avoid phantom diffs.
    if raw.endswith(b"\n"):
        out += "\n"
    sys.stdout.buffer.write(out.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
