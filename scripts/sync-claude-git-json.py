#!/usr/bin/env python3
"""Snapshot the versionable slice of a live .claude.json into .claude-git.json.

Claude Code owns .claude.json: it rewrites the file constantly (atomically, via
rename) and stores OAuth session data, machine/user identifiers, and an entry for
every local project alongside the handful of keys actually worth versioning. So
that file is not tracked. This script copies the whitelisted keys out of it into
.claude-git.json, which IS tracked -- a snapshot no git operation can write back
over the live config.

Usage:  sync-claude-git-json.py --source <live .claude.json> --out <.claude-git.json>

Exits 0 and leaves --out untouched if the source is missing or unparseable, so a
pre-commit hook never blocks a commit over it.
"""
import argparse
import collections
import json
import sys

# Only these top-level keys are versioned. Everything else in .claude.json is
# either machine-local identity, an OAuth session, or per-project state.
KEEP = ("mcpServers",)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="live .claude.json to read")
    ap.add_argument("--out", required=True, help=".claude-git.json to write")
    args = ap.parse_args()

    try:
        with open(args.source, encoding="utf-8") as fh:
            data = json.load(fh, object_pairs_hook=collections.OrderedDict)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"sync-claude-git-json: skipping ({exc})", file=sys.stderr)
        return 0

    kept = collections.OrderedDict((k, data[k]) for k in KEEP if k in data)
    new = json.dumps(kept, indent=2, ensure_ascii=False) + "\n"

    try:
        if open(args.out, encoding="utf-8").read() == new:
            return 0  # unchanged; leave mtime alone
    except OSError:
        pass

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(new)
    print(f"sync-claude-git-json: refreshed {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
