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
