## System-Specific Commands

This system aliases standard commands. **Always** call them through the `command`
builtin: `command tail`, `command head`, `command rm`, `command cat`, `command grep`,
`command ls`, `command cp`, `command mv`, `command find`, and any other standard command.

Use POSIX syntax for `tail` and `head`: `tail -n 10`, not `tail -10`.

## Build Scripts — Always Log to File

Never pipe a long build, test or compile command (`./build-dev.sh`, `./mvnw …`,
`./gradlew …`, `npm run build`, `cargo build`, anything over a few seconds) straight into `tail`.
Write the full output to a timestamped log under `./tmp/claude-logs/`, then read the file:

```bash
mkdir -p ./tmp/claude-logs && LOG=./tmp/claude-logs/<name>-$(date +%Y%m%d-%H%M%S).log && <command> > "$LOG" 2>&1
```

The timestamp is mandatory, so reruns never collide. Then `command tail -n 80 "$LOG"`;
investigate earlier output with `Read` / `Grep` on the log instead of rerunning. Report the
log path to the user.

**Why:** a failure above the tail window otherwise forces a full rebuild just to see the error.

## Validate With The Repo's Full-Build Script Before Pushing

Before a push or PR in a backend repo, run its full-build script from the repo root at least
once, even if module-level `mvn` / `./gradlew` tests already passed: `./build-project.sh` for
Spring Boot backends (e.g. `inventory-backend`), `./build-dev.sh` for Quarkus backends. Check
for it at the start of a session in the repo, and log it as above.

**Why:** a change can pass in one module and break a downstream one (e.g. flip an error code in
`api-services`); the scripts also build the Docker images and catch packaging issues.

## Self-Review At The End Of Every Code Task

**Златното правило — the first version of the code always misses something.** When a code
task is done, review it before you report it as ready and before you ask "shall I proceed?".
Do not wait to be asked. Read the whole diff back as if someone else wrote it. A green test suite is not a substitute: the tests only cover the cases
you already thought of.

Follow the `self-review` skill: collect findings, **revalidate each one against the actual
source before touching anything**, fix only the confirmed ones, and report every finding with
its outcome, fixed or rejected.

**Why:** review passes, especially by subagents, produce plausible findings that are wrong;
fixing an unconfirmed one changes working code for no reason.

## Do Not Create GitHub Repos Without Explicit Permission

Do not run `gh repo create` (or any `gh` command that creates a repository) unless the user
explicitly asked to create a GitHub repo. "commit and push" is not permission. If `origin` is
missing, commit locally, say there is no remote, and wait.

Do not pick a GitHub account from the current `gh auth` default. Personal repos go to
`idachev` (`git@github-idachev:idachev/...`), not `ivan-mentorano`, unless the user named
that org.

## Plans And Specs Live In `docs/plans/`, Finished Ones In `docs/plans/done/`

Superpowers brainstorming specs and writing-plans plans go to `docs/plans/` in the repo, not
to `docs/superpowers/specs/` or `docs/superpowers/plans/`. This overrides the skills' default
paths. Keep their file naming: `YYYY-MM-DD-<topic>-design.md` for a spec,
`YYYY-MM-DD-<feature>.md` for a plan.

When a plan is implemented and merged, `git mv` its plan and spec to `docs/plans/done/` and
fix the relative links between them. Do not do it on your own judgment: only when Ivan says it
is done, or all the plan's steps are verified complete.

## Serena Is The Default Lens On Code

When a task touches **code**, use the `serena` MCP tools as the primary way to read, search and
change it: `get_symbols_overview` before reading a file whole, `find_symbol` /
`find_referencing_symbols` / `find_implementations` instead of `grep` for definitions,
callers and implementations, `rename_symbol`,
`replace_symbol_body`, `insert_after_symbol`, `safe_delete_symbol` instead of `sed` or
line-number edits, `get_diagnostics_for_file` after an edit.

Keep `grep` / `rg` / `sed` for what genuinely is text: docs and markdown, config values, logs,
`.env` templates, commit messages, shell scripts.

**Why:** text search misses references that arrive through aliases, re-exports or inheritance,
and gives false hits in comments and strings; serena answers from the symbol graph.

If the serena tools are deferred, load the ones you need with **one** batched `ToolSearch`
call before starting the code work.

## Number Every Item In Every List

Every user-facing item gets a topic ID: two Cyrillic letters plus a number, so Ivan can answer
"ВР1" instead of quoting the text back. This covers list items (the **Списък** section too),
questions, answer options, status lines, open points, and entries written into a project TODO
file.

- Choose the letters by the item's topic: `ВР1` for time, `ГР2` for scope boundaries, `ОП1`
  for answer options.
- Items of one topic share the letters and count up (`ВР1`, `ВР2` …), so no two items share an
  ID.
- Keep an item's ID when it comes back later in the same reply, and in a follow-up reply that
  returns to the same item. Reuse the ID already in a TODO file.
- Review findings may stay `F1`, `F2` ….
- Plain numbers and unlabelled bullets ("- Отворено: …") are not enough.

**Why:** without IDs Ivan has to copy an item's text to point at it; plain numbers clashed with
the TODO file's own numbering, and Latin one-letter prefixes carry no topic.

## One-By-One Passes Close Every Decision

When Ivan asks to go through findings one by one and to ask him about anything that changes
behaviour, the goal is to close every decision. If fixing a finding brings up a new choice (a
new name in the ubiquitous language, a missing button, an unknown fact), ask it right there as
the next one-by-one question. Do not collect such points into an "open points" list in the
final report. Only a question Ivan cannot answer or explicitly defers stays in the report,
marked as deferred; never invent the answer.

## Codex Facts

- Model id `gpt-6-astra`. "astra" is what people say, but `--model astra` fails with HTTP 400;
  always pass the full id.
- Effort: pass it explicitly (the config default is `high`). `medium` by default; `high` only
  for review of very complex specs or implementations, critical actions, or complex consensus.
- Direct CLI (the shell aliases `codex`):
  `command timeout 1200 codex exec -m gpt-6-astra -c model_reasoning_effort=medium -s read-only -C <repo> -o <log>.final.md - < prompt.md > <log> 2>&1`,
  log in `./tmp/claude-logs/` with a timestamp; tell it not to browse the web.

## Commands For Ivan To Run Go In Their Own Code Block

When Ivan has to run a command, put it alone in a fenced code block, one command per block
(with the `! ` prefix when it is meant for this session's prompt). Never put it inline in a
sentence or list item, and never put punctuation or prose on the same line. Prose before the
block says what it does; the next step goes after the block.

**Why:** Ivan copied `... -f ack_deploy_changes=true. deploy/classify.sh` from an inline list
item; the trailing full stop came along and GitHub refused the dispatch with HTTP 422.
