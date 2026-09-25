---
name: self-review
description: Use when the user asks for a self review of the current branch, says "ревю на промените" or "провери дали сме покрили всичко", wants review findings revalidated against the real code before anything is fixed, or is about to hand a branch over and wants it checked first.
---

# Self Review

Review the current branch, then work through the findings one at a time. A finding is fixed only
after it is revalidated against the real code. Nothing is committed.

## When not to use

- The user wants the review alone, with no fixes. Run `/code-review` directly and report.
- The user wants the branch checked against a written plan and reported, not fixed. Compare the
  diff with the plan under `docs/plans/` and report the gaps; change nothing.
- The branch has no commits yet, so there is no diff against the base.
- The user asks for a commit, a push or a PR. This skill never does those.

## Step 1 — Review

- Run `/code-review` on the current branch. Base branch is `master` unless the user names
  another.
- Consolidate all agent findings into one numbered list. Deduplicate. For each entry keep:
  `file:line`, the claim, the severity, the proposed fix.
- Check ticket coverage when the branch name carries a ticket key. List the ticket's requirements,
  then add a finding for each requirement the diff does not cover.
  - Read the ticket with `mcp__atlassian__getJiraIssue` **only if that tool is present**. The
    Atlassian MCP server comes from a plugin that is disabled in this setup, so in a normal
    session the tool does not exist.
  - When it is missing, do not stop and do not guess the requirements. Ask the user to paste the
    ticket, or fall back to the design doc under `docs/plans/`.
  - Name the source you used in the report. When coverage could not be checked at all, say that
    plainly instead of leaving it implied.
- Check the repo's last full build log under `./tmp/claude-logs/` to know whether HEAD is green.
- Do not fix anything in this step. Present the list to the user only if they asked for the review
  alone; otherwise continue.

## Step 2 — Revalidate and act, one finding at a time

Repeat for every finding, in list order. Never batch several unvalidated findings into one fix.

### 2.1 Take the first unprocessed finding.

### 2.2 Revalidate it against the real code, not the diff excerpt.

- Read the full method and its callers. Trace the flow end to end, including flows the diff did
  not touch (delayed paths, retries, fallbacks).
- Check the existing tests and fixtures that cover that path.
- When the finding is about a rule, a limit or a field, check the source of truth:
  `docs/CONTEXT.md`, `docs/plans/*.md`, the external contract (OpenAPI yaml), and the dependency
  jars in `~/.m2` for the version the pom actually uses.
- Decide one verdict:

| Verdict | Meaning | Action |
|---|---|---|
| **VALID** | The problem is real in the code as it is | Fix it now: code, tests and docs together. Run `spotless:apply` and the affected test classes. |
| **INVALID** | The code already behaves correctly, or the claim is wrong | Change nothing. Record why, with evidence: `file:line`, test name, contract line. |
| **DECISION** | The finding contradicts a decision recorded in the design doc, or needs product input | Change nothing. Record the question for the user. |

- Log every Maven run to `./tmp/claude-logs/<name>-$(date +%Y%m%d-%H%M%S).log`. Follow the
  `java-stack:java-maven` skill for flags and wrapper use.
- When a test run fails at discovery ("Could not load class") with a wildcard `-Dtest` pattern,
  rerun with explicit class names and `-am` before suspecting the code.

### 2.3 Mark the finding processed and go to the next one.

## Step 3 — Close

- Run the repo's own full-build script once, so packaging and downstream modules are covered too:
  `./build-dev.sh` (Quarkus), `./build-project.sh` (Spring). For a frontend repo run the build and
  test scripts the repo declares in `package.json`. Log the output to
  `./tmp/claude-logs/build-<timestamp>.log` and report the test count and result.
- When the repo has no full-build script, run the test suite instead and say in the report that no
  full build exists. Never report a green build you did not run.
- Report a table: `# | finding | verdict | action taken | evidence`.
- List the DECISION items as questions for the user.
- Do not commit or push. The user asks for that separately.

## Rules

- Every claim in the report points to a `file:line`, a test, or a log line.
- Do not re-open decisions recorded in the design doc. List them under DECISION instead.
- Comments and Javadoc carry only facts the code cannot show. Cite Jira keys, never plan step
  numbers. See `java-stack:java-comments`.
- A finding that only restates an accepted trade-off from the design doc is INVALID, not a fix.
- If the user answers a DECISION item, treat the answer as final and apply it without re-arguing.
