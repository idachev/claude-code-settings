---
name: self-review
description: Self review of the current branch against its base, then a one-at-a-time revalidate-and-fix loop over every finding. Use when the user asks for a self review, "ревю на промените", "провери дали сме покрили всичко", or wants review findings revalidated before they are fixed. Runs the multi-agent diff review, checks ticket coverage, revalidates each finding against the real code, fixes only what holds, and reports the rest with evidence. Never commits.
---

# Self Review

Review the current branch, then work through the findings one at a time. A finding is fixed only
after it is revalidated against the real code. Nothing is committed.

## Step 1 — Review

- Run `/sc-sdlc:be-review-diff` for a Java backend repo, or the matching diff review skill for
  the repo type. Base branch is `master` unless the user names another.
- Consolidate all agent findings into one numbered list. Deduplicate. For each entry keep:
  `file:line`, the claim, the severity, the proposed fix.
- Load the Jira ticket named in the branch (`mcp__atlassian__getJiraIssue`). List its
  requirements so coverage can be checked against them. Add a finding for each requirement the
  diff does not cover.
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

- Run the repo full build once: `./build-dev.sh` (Quarkus) or `./build-project.sh` (Spring), with
  the output in `./tmp/claude-logs/build-dev-<timestamp>.log`. Report the test count and result.
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
