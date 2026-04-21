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

@RTK.md
