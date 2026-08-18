#!/bin/sh
# Install the local git plumbing this repo needs. Filters and hooks live in
# .git/, which git itself cannot version, so a fresh clone must run this once.
#
#   scripts/install-hooks.sh [path-to-live-.claude.json]
#
# Installs:
#   - a clean filter that strips runtime/company-derived keys from settings.json
#     on their way to the index (see scripts/git-clean-json.py)
#   - a pre-commit hook that refreshes the tracked .claude-git.json snapshot from
#     the live .claude.json (see scripts/sync-claude-git-json.py)
set -e

repo="$(cd "$(dirname "$0")/.." && pwd)"

# Claude Code keeps its state file at $CLAUDE_CONFIG_DIR/.claude.json when that
# variable is set, and at ~/.claude.json otherwise -- note the default lives in
# the home directory, NOT inside ~/.claude.
if [ -n "$1" ]; then
  live="$1"
elif [ "$repo" = "$HOME/.claude" ]; then
  live="$HOME/.claude.json"
else
  live="$repo/.claude.json"
fi

if [ ! -f "$live" ]; then
  echo "install-hooks: no live config at $live" >&2
  exit 1
fi

git -C "$repo" config filter.strip-settings.clean "python3 $repo/scripts/git-clean-json.py settings"
git -C "$repo" config filter.strip-settings.smudge cat

cat > "$repo/.git/hooks/pre-commit" <<HOOK
#!/bin/sh
# Refresh the tracked snapshot of the live .claude.json before each commit.
# Not versioned (hooks live in .git/) -- reinstall on a fresh clone with:
#   scripts/install-hooks.sh
set -e
repo="\$(git rev-parse --show-toplevel)"
python3 "\$repo/scripts/sync-claude-git-json.py" \\
  --source "$live" \\
  --out "\$repo/.claude-git.json"
git add -- "\$repo/.claude-git.json"
HOOK
chmod +x "$repo/.git/hooks/pre-commit"

echo "install-hooks: settings.json clean filter configured"
echo "install-hooks: pre-commit hook installed (live config: $live)"
