#!/usr/bin/env python3
"""Git clean filter: strip company-derived keys from settings.json before staging.

Claude Code's auto-mode "environment" learning rewrites settings.json at runtime with
an inventory of whatever org infrastructure it has seen -- cluster names, buckets,
protected branches, CI secret names. That must not reach the index. This filter runs
on the worktree -> index path only (`git add`, `git diff`, `git status`); the working
file keeps everything.

Usage (from .gitattributes + .git/config):  git-clean-json.py settings

The live .claude.json is not tracked at all -- a pre-commit hook snapshots its
versionable slice into .claude-git.json instead. See scripts/sync-claude-git-json.py.

Fails open: if stdin is not parseable JSON, it is passed through byte-for-byte
rather than risking a corrupted commit.
"""
import collections
import json
import sys

SETTINGS_DROP = ("autoMode",)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    raw = sys.stdin.buffer.read()

    if mode != "settings":
        sys.stdout.buffer.write(raw)
        return 0

    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=collections.OrderedDict)
    except (UnicodeDecodeError, json.JSONDecodeError):
        sys.stdout.buffer.write(raw)
        return 0

    for key in SETTINGS_DROP:
        data.pop(key, None)

    out = json.dumps(data, indent=2, ensure_ascii=False)
    # Match the source file's trailing-newline convention to avoid phantom diffs.
    if raw.endswith(b"\n"):
        out += "\n"
    sys.stdout.buffer.write(out.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
