# Artifacts: Keep A Copy Of The Source In Git

Read this before you publish or republish a claude.ai artifact (the `Artifact` tool), in any project.

## The rule

Every claude.ai artifact published for Ivan gets a copy of its source in the git repository of the
project it belongs to. Do it without being asked, in the same piece of work as the publish.

**Why:** the published page lives only on claude.ai, and its local source sits in the session
scratchpad, which a reboot clears. Ivan, 2026-11-15: „запомни всички артифакти които искам да имат
копие в гит, виж къде сме слагали други и там сложи и този“.

## Where

1. If the repository has its own artifact rule (for example `docs/agents/artifacts.md`, referenced
   from its `CLAUDE.md` or `AGENTS.md`), follow it. It wins over this file.
2. Otherwise look for earlier artifact copies (usually `docs/artifacts/`) and put the new one next to
   them, in the same shape.
3. If there are none, use `docs/artifacts/`. Ask Ivan only when the work belongs to no repository.

Shape:

- A single-file page: `docs/artifacts/<name>.html`.
- A page with pictures or other files: `docs/artifacts/<name>/index.html` plus its `img/` (or other
  folders), with the same relative paths the published page uses.

## How

- Save the copy in the publish form (as passed to the `Artifact` tool, for example starting with
  `<title>` and no doctype), so the page can be republished to the same URL from the copy.
- Write the artifact's URL next to the copy: in the repository's document index if it has one (for
  example `docs/agents/docs.md` or `docs/artifacts/README.md`), and as a link in the plan or doc the
  artifact belongs to.
- When the page changes, republish from the copy and update the copy in the same commit.
- Artifacts made from an Artifact type (slides, docs): copy the data files you published, not the
  type's own files.
- Never copy secrets, tokens or personal data that are not meant for the repository. If the page holds
  them, ask Ivan first.
- Commit the copy like any other doc change; push only under the project's usual rules.
