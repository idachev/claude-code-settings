# .claude

My personal [Claude Code](https://docs.claude.com/en/docs/claude-code) configuration — global instructions, settings, and skills.

This is a snapshot of `~/.claude` minus runtime state, conversation history, and credentials (see `.gitignore`).

## What's in here

| File / Dir | Purpose |
|---|---|
| `CLAUDE.md` | Global instructions injected into every Claude Code session (shell-alias bypass rules, build-log conventions, etc.) |
| `RTK.md` | Notes on [RTK (Rust Token Killer)](https://github.com/rtk-ai/rtk) — a CLI proxy that reduces token usage |
| `settings.json` | Hooks, enabled plugins, marketplaces, status line |
| `skills/hashtag-researcher/` | Custom skill for researching social-media hashtag popularity (handles Latin + Cyrillic) |
| `skills/agent-browser`, `skills/find-skills`, `skills/skill-creator` | Symlinks into `~/.agents/skills/` — installed via the [vercel-labs/skills](https://github.com/vercel-labs/skills) CLI (see [Replicating the `~/.agents` skills](#replicating-the-agents-skills) below). **Dangling after clone** until you install them. |

## Heads-up before copying my `settings.json`

A few settings here suit my workflow but may not suit yours:

- `"skipDangerousModePermissionPrompt": true` and `"skipAutoPermissionPrompt": true` disable some permission prompts. Only keep these if you understand what they mean.
- The hook commands reference local scripts that are **not in this repo**:
  - `~/bin/claude-input-notify.sh`
  - `~/bin/claude-bash-safety.sh`
  - `~/bin/claude-statusline.sh`

  These `~/bin/...` scripts live in my [own-debian-configs](https://github.com/idachev/own-debian-configs) repo.
  - `bd prime` (from the [beads](https://github.com/steveyegge/beads) plugin)
  - `rtk hook claude` (from [RTK](https://github.com/rtk-ai/rtk))

  Remove or replace these before using the config, or Claude Code will fail when the hooks fire.
- The `enabledPlugins` list reflects my marketplaces (including private ones like `sc-marketplace`). You'll want to prune to what you actually have access to.

## Replicating the `~/.agents` skills

The three symlinks under `skills/` (`agent-browser`, `find-skills`, `skill-creator`) point at `~/.agents/skills/<name>/`. That directory is managed by the [`skills` CLI](https://github.com/vercel-labs/skills) from Vercel Labs — a multi-agent skills installer that shares a single skill set across Claude Code, Codex, Cursor, OpenCode, and others.

To replicate my install:

```bash
# Installs the agent-browser SKILL + bundled skill-creator
npx skills add vercel-labs/agent-browser

# Installs find-skills (lives in the vercel-labs/skills repo)
npx skills add vercel-labs/skills
```

The CLI writes everything to `~/.agents/skills/<name>/` and tracks versions in `~/.agents/.skill-lock.json`. After install, the symlinks in this repo will resolve correctly.

To verify what got installed:

```bash
cat ~/.agents/.skill-lock.json
ls ~/.agents/skills/
```

## What's deliberately gitignored

Anything that would leak credentials, conversation content, or machine-local state:

- `.credentials.json` — OAuth tokens
- `history.jsonl`, `projects/`, `sessions/`, `todos/`, `tasks/`, `shell-snapshots/`, `file-history/`, `paste-cache/` — conversation and session state
- `logs/`, `telemetry/`, `usage-data/`, `statsig/`, `stats-cache.json` — telemetry
- `plans/` — private project notes
- `plugins/`, `cache/`, `backups/`, `downloads/`, `ide/` — reproducible / machine-local

See `.gitignore` for the full list.

## License

Personal config — use any part you like as a reference. No warranty.
