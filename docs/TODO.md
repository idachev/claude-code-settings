# TODO

Open work for the personal Claude Code setup in `~/.claude`. Each entry has an ID of two Cyrillic
letters plus a number; before adding one, check that the ID is not used here or in `git log`.

## СГ1 - rotate `GITHUB_TOKEN_MENTORANO_READONLY`, its value is in session transcripts

Added 2026-11-18. Ivan asked to change the token.

- Why: the full value of `GITHUB_TOKEN_MENTORANO_READONLY` is in plain text in at least one old
  session transcript (`~/.claude/projects/**/*.jsonl`, next to `CHOKIDAR_USEPOLLING=1
  CHOKIDAR_INTERVAL=10000`) and in the transcript of session `4d39987e-3030-4be9-9688-8d596c0743c0`
  (the process-load analysis of 2026-11-18). The token is read-only, but it reads every private
  Mentorano repo. The order of the variables suggests a process environment listing (`pgrep -fl`,
  `ps eww`, `ps -E`) printed it, not a command that set it; not confirmed.
- Open:
  1. Make a new read-only token in GitHub for the same repos, then revoke the old one.
  2. Find where the variable is set (it is in the live environment, but not in `~/.zshrc`,
     `~/.zshenv`, `~/.zprofile`, `~/.bash*`, `~/.profile` or `~/.claude/settings*.json`; check
     `launchctl getenv`, Supacode's environment, a keychain or `.env` loader) and put the new value there.
  3. Find the session commands that printed process environments and stop that pattern. Seen on
     2026-11-18: `pgrep -fl` on an `npm exec wrangler …` process printed environment variables
     after its arguments (`npm exec` rewrites its process title), so `ps -o args` / `pgrep -fl` of
     such a process can leak too; list with `-o comm` or cut the line (`cut -c1-200`).
  4. Decide with Ivan whether to scrub the old value from the transcripts (it is dead once revoked).
