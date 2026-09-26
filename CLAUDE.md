## System-Specific Commands

### Bypassing Shell Aliases
This system has aliases for standard bash commands. **ALWAYS** use the `command` builtin to bypass aliases and execute the actual system commands:

```bash
# Correct - bypasses aliases
command tail -n 50 file.txt
command head -n 100 file.txt
command rm file.txt
command cat file.txt
command grep pattern file.txt

# Wrong - may use aliased versions
tail -n 50 file.txt
rm file.txt
```

**Critical**: Apply this to ALL standard bash commands including but not limited to: `tail`, `head`, `rm`, `cat`, `grep`, `ls`, `cp`, `mv`, `find`

### POSIX-Compliant Syntax
Use POSIX-compliant syntax for `tail` and `head`:
- Use `tail -n 10` (not `tail -10`)
- Use `head -n 10` (not `head -10`)

## Build Scripts — Always Log to File

**Never** run long build scripts (e.g. `./build-dev.sh`, `./mvnw …`, `./gradlew …`, `npm run build`, `cargo build`, anything that takes more than a few seconds) by piping straight into `command tail`. Always redirect full output to a **timestamped** log file under `./tmp/claude-logs/` first, then inspect the file.

**Why:** If the build output is only piped to `tail`, a failure buried above the tail window forces a rerun of the entire build to re-capture the error. Rebuilds can take many minutes. Writing to a file once lets you re-read any part of the output as many times as needed without rerunning.

**Why `./tmp/claude-logs/` + timestamps:** Keeps all Claude-generated script logs in one organized, gitignorable directory so they don't pollute the project's own `./tmp/` scratch area. Timestamped filenames mean consecutive runs never collide — you never have to `rm -f` a stale log or hit a `noclobber` error, and the chronological history of build attempts is preserved automatically.

**How to apply** — every time you invoke a build/test/compile script:

1. Ensure `./tmp/claude-logs/` exists: `mkdir -p ./tmp/claude-logs`.
2. Run the script with full output captured to a **timestamped** file, e.g.:
   ```bash
   mkdir -p ./tmp/claude-logs && ./build-dev.sh > ./tmp/claude-logs/build-dev-$(date +%Y%m%d-%H%M%S).log 2>&1
   ```
   The `$(date +%Y%m%d-%H%M%S)` suffix is **mandatory**, not optional — it prevents overwrite-without-clobber errors on reruns and preserves run history.
3. Capture the log path into a variable (or re-derive it) so subsequent `tail` / `Read` / `Grep` calls reference the exact file you just wrote.
4. After the command finishes, `command tail -n 80 <logfile>` to see the summary.
5. If anything looks wrong, use `Read` / `Grep` on the log file to investigate — **do not** rerun the build just to see earlier output.
6. Report the log file path to the user so they can inspect it too.

This applies to every project, not just one. Treat `./tmp/claude-logs/*.log` as the canonical record of Claude's build runs, sorted chronologically by filename.

## Validate With The Repo's Full-Build Script Before Pushing

Before pushing or opening a PR in a backend repo, check for a full-build script in the repo root and run it at least once, even if module-level `mvn`/`./gradlew` tests already passed:

- **Spring Boot backends**: `./build-project.sh` (e.g. `inventory-backend`)
- **Quarkus backends**: `./build-dev.sh`

**Why:** A change can pass in an isolated module's test run while breaking a downstream module — e.g. a validation check moved earlier in a call chain can preempt a more specific check elsewhere and flip its error code, only visible once the full reactor (or a downstream module like `api-services`) runs. These scripts also build the project's Docker image(s), catching packaging issues a plain test run wouldn't. Log to a timestamped file per the rule above; don't pipe straight to `tail`.

**How to apply**: at the start of a session in a repo, check whether `build-project.sh` or `build-dev.sh` exists in the repo root. If one does, run it before any push/PR — not just the module(s) you touched.

## Self-Review At The End Of Every Code Task

When you finish any code task, run a self-review before reporting completion. Do not wait to be asked.

**Златното правило — the first version of the code always misses something.** The review is
mandatory the moment a first implementation is finished, and it happens **before** you report
the work as ready and **before** you ask "shall I proceed?". A green test suite is not a
substitute: the tests only cover the cases you already thought of. Read the whole diff back as
if someone else wrote it, hunt for what the tests do not cover, then follow the order below.

**Order matters — revalidate before you fix:**

1. Review the code you just wrote or changed and collect findings.
2. Take each finding one at a time and **revalidate it against the actual source** before touching anything.
3. If the finding is confirmed, fix it.
4. If the finding does not hold up, **do not fix it**. Report that you checked it and it was not a real problem, then move to the next finding.

**Why:** review passes — especially ones run by subagents — produce plausible-sounding findings that are wrong. Fixing an unconfirmed finding changes working code for no reason and can introduce real bugs. A finding earns a fix only after it survives a second look at the source.

Report the outcome of every finding, both the ones you fixed and the ones you rejected, so the review's actual coverage is visible and not just the diff.

## Do Not Create GitHub Repos Without Explicit Permission

Do not run `gh repo create` (or any `gh` command that creates a
repository) unless the user explicitly asked to create a GitHub repo.

"commit and push" is not permission to create a repo. If `origin` is
missing, commit locally and stop. Say there is no remote. Wait.

Do not pick a GitHub account from the current `gh auth` default. Personal
repos go to `idachev` (`git@github-idachev:idachev/...`), not
`ivan-mentorano`, unless the user named that org.


## Plans And Specs Live In `docs/plans/`, Finished Ones In `docs/plans/done/`

Superpowers brainstorming specs and writing-plans plans go to `docs/plans/`
in the repo, not to `docs/superpowers/specs/` or `docs/superpowers/plans/`.
This overrides the default paths in the superpowers skills. Keep the skills'
file naming: `YYYY-MM-DD-<topic>-design.md` for a spec,
`YYYY-MM-DD-<feature>.md` for a plan.

When a plan is implemented and merged, move its plan and spec to
`docs/plans/done/` with `git mv`, and fix any relative links between them.
`docs/plans/` then holds only work that is still open, so a glance at the
directory shows what is in flight.

Do not move a plan to `done/` on your own judgment. Ivan says when it is
done, or the plan's own steps are all verified complete.

## Serena Is The Default Lens On Code

When a task touches **code**, use the `serena` MCP tools as the primary way to
read it, search it, and change it. Text tools are the fallback, not the default.

Serena reads through a language server, so it works on the same symbol tree the
compiler sees. `grep`, `rg` and `sed` only see lines of characters. That gap
matters for reading, for searching, and for editing alike.

**Reach for serena whenever you would otherwise reach for a text tool on code:**

- Understanding an unfamiliar file → `get_symbols_overview` before reading it
  whole; then `find_symbol` with `include_body` for just the part you need.
  This is usually cheaper and more accurate than dumping the file.
- "Who calls this?" / "is this still used?" → `find_referencing_symbols`. This is
  the case text search gets wrong most often, in both directions.
- Where is this defined? → `find_symbol`, `find_declaration`.
- What implements this interface or base class? → `find_implementations`.
- Renaming across the project → `rename_symbol`, not a `sed` sweep.
- Replacing a function or method body → `replace_symbol_body`.
- Adding code next to an existing symbol → `insert_before_symbol` /
  `insert_after_symbol`, instead of counting line numbers.
- Removing something → `safe_delete_symbol`, which refuses when references
  remain and tells you what they are.
- Project-wide textual edits that still need to be precise → `replace_content` /
  `replace_in_files`.
- Checking a file compiles clean after an edit → `get_diagnostics_for_file`.

**Keep `grep` / `rg` / `sed` for what genuinely is text** and has no symbol
nature: prose in docs and markdown, values and keys in config files, log file
contents, `.env` templates, commit messages, shell scripts.

**Why.** Text search finds lines, not meanings. It produces false hits — the
word inside a comment, a string literal, or a longer unrelated identifier — and
at the same time it misses real ones, because a reference can arrive through an
import alias, a re-export from another module, a decorator, or inheritance. Both
errors are expensive in opposite ways: a missed reference leads to deleting or
renaming something that is still in use, while a false hit leaves dead code
alive and wastes a review. Text editing has the mirror problem: a `sed` rename
touches the string wherever it appears, including places that merely contain it.
Serena answers from the symbol graph, so it is both complete and free of that
noise, and its edits land on the symbol rather than on the characters.

If the serena tools are deferred in a session, load the ones you expect to need
with **one** batched `ToolSearch` call before starting the code work — not one
call per tool.

## Number Every Item In Every List

Every item in every user-facing list gets a short unique ID, so Ivan can
answer "точка 3" instead of quoting the text back. This covers the
**Списък** section, review findings, options, open points and questions.

- Number items continuously across the whole reply (1, 2, 3 …), so no two
  items share an ID, even across sub-lists. Review findings may use F1, F2 ….
- Keep an item's ID when it comes up again later in the same reply, and in
  a follow-up reply that returns to the same item.
- Plain unlabelled bullets ("- Отворено: …") are not enough.

**Why:** Ivan has asked for this several times. Without IDs he has to copy
the item's text to point at it.

## Close Every Decision Inside A One-By-One Pass

When Ivan asks to go through review findings one by one and to ask him about
anything that changes behaviour, the goal of that pass is to close every
decision. If fixing a finding brings up a new choice (a new name in the
ubiquitous language, a missing button, an unknown fact such as the phone
model), ask it right there as the next one-by-one question. Do not collect such
points into an "open points" list in the final report.

**Why:** after one such pass Ivan asked, surprised, why there were still open
points when the pass was meant to close them. Leftover points force a second
round that he expected to be unnecessary.

## New Personal Android Apps Start From The Official Template

Start every new personal Android app from the official Google template, not
from a hand-written Gradle setup. First update the Android CLI
(`android update`, binary in `~/.local/bin/android`) so the template is the
latest one. Then run `android create empty-activity --name="<App Name>"`. The
template gives the package `com.example.<name>`; Ivan's apps use
`com.idachev.<name>`.

Take the structure and build conventions from `~/develop/personal/financy`:
`build-project.sh` (unit tests + debug APK, timestamped log), a `CLAUDE.md` in
Bulgarian, `docs/CONTEXT.md` as the ubiquitous-language glossary, manual DI
through `AppContainer`, debug-only builds, and a deploy script that copies a
timestamped APK to `~/Dropbox/mobile/idachev/<app>/` and moves older ones to
`old/` (see `scripts/deploy-apk.sh` in `meet-no-miss`).

**Why:** the template's version set is known to compile, and shared
conventions keep Ivan's apps consistent.

## Second-Opinion Reviews Go Through Codex With `gpt-6-astra`

When Ivan asks for a review or a second opinion from another model, use
Codex. It handles reviews better than the other CLIs he tried. Ivan calls the
model "astra", but the id Codex accepts is **`gpt-6-astra`**. The bare name
fails with `The 'astra' model is not supported when using Codex with a ChatGPT
account.` Always pass the full id, even though it is also the default in
`~/.codex/config.toml`, so the call does not depend on that file.

- Plugin, through `codex:codex-rescue`: start the prompt with
  `--model gpt-6-astra --effort medium`, then the read-only review request.
  Ivan's usual effort for reviews is `medium` (the config default is `high`).
- Direct CLI, when the prompt is long or needs extra repos:
  `command codex exec -m gpt-6-astra -s read-only -C <repo> -o <log>.final.md - < prompt.md > <log> 2>&1`,
  with the log in `./tmp/claude-logs/` and a timestamp in the name.
- `/codex:review` takes only `--wait|--background`, `--base` and `--scope`,
  and passes `--model` through raw. It has no `--effort` and no focus text; use
  `/codex:adversarial-review` or `codex exec` when a focus is needed.
- A review can take 10+ minutes: run it in the background or with a 600000 ms
  timeout.
- Codex runs on Ivan's ChatGPT account and can hit its usage limit ("You've
  hit your usage limit … try again at …"). Do not stop and wait for Ivan. Fall
  back in this order, each one only when the previous one fails or has no
  usage left:
  1. grok: `command grok -p "<prompt>" --cwd <repo>` (check `grok models` for
     the newest model and pass it with `-m`);
  2. agy: `command agy -p "<prompt>" --model <newest from agy models> --print-timeout 300s`;
  3. a fresh Claude subagent (Agent tool) with no context from this session,
     so its review is independent.
  Tell Ivan afterwards which reviewer ran and why.
- Exception — large blast radius: if the change is big or risky (many files, a
  data migration, deletions, anything hard to undo) and Codex is out of usage,
  stop and wait for Ivan instead of relying on a fallback review. Say when the
  Codex quota resets.
- Complex task: use 2 or 3 reviewers instead of one (Codex plus grok, agy or
  a fresh Claude subagent). Merge their findings, then hold a consultation:
  send each reviewer the findings of the others and ask which ones it confirms
  or disputes, and why. A finding that two reviewers agree on weighs more; a
  disputed one gets a closer look at the source before any fix.
- Check every Codex finding against the source before fixing it (see
  Self-Review above).
