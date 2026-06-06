---
name: beads-impl
description: Execute an implementation plan by chopping it into beads (bd issues), implementing them with parallel subagents where safe, and finishing with a self-review. Use when the user provides a plan file and asks to implement it via beads, "chop the plan into beads", "do the beads impl", or wants plan execution tracked as bd issues with dependency-aware parallel subagents. The plan file path is passed as the argument.
---

# Beads Impl

**Argument**: path to the plan file. If missing, ask for it before doing anything else.

## Step 1: Load the supporting skills

Invoke via the Skill tool — they define the mechanics this workflow relies on:

1. `beads:beads`
2. `superpowers:subagent-driven-development`
3. `superpowers:dispatching-parallel-agents`

Follow those skills for all bd usage and subagent mechanics. Only the deviations below override them.

## Step 2: Read the plan

Read the plan file and anything it references — bead descriptions must stand alone since subagents won't see this conversation.

## Step 3: Branch setup

Before creating beads or touching code:

- If the user already stated which branch to use (this prompt or earlier), follow that — don't re-ask.
- If on the default branch: create a feature branch named after the plan and tell the user.
- Otherwise: ask whether to continue on the current branch or create a new one.

## Step 4: Chop the plan into beads

Create one bead per coherent unit of work (typically a plan phase/task), with dependencies mirroring the plan's real ordering — don't add artificial edges between independent tasks, since dependencies gate parallelism.

Add one final bead, **"Self-review of implementation"**, dependent on all others: review the full diff against the plan, verify every requirement, run tests/linters, fix gaps.

Show the user the bead list with dependencies before implementing.

## Step 5: Implement the beads

Work through `bd ready` rounds per the loaded skills, with two constraints:

- Parallelize only beads whose file footprints don't overlap; when uncertain, run sequentially.
- Include the user's implementation instructions (TDD, style, commit conventions) in every subagent prompt.

## Step 6: Self-review (main session, not a subagent)

Execute the final self-review bead yourself, in this session — the value is reviewing with full context of everything that just happened, which a fresh subagent lacks. Then report: beads closed, branch, test results, any deviations from the plan.
