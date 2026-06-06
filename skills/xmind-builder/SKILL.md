---
name: xmind-builder
description: Use when the user asks to create, generate, or build a mind map / .xmind file, convert an outline into a mind map, or produce an .xmind from a topic or brief. Trigger phrases - "build an xmind", "make a mind map", "create .xmind", "turn this outline into a mindmap". Cyrillic and other Unicode work without flags.
---

# xmind-builder

Generate `.xmind` files via the official `xmindmark` CLI — concise markdown-like source compiles to a `.xmind` that opens in the XMind desktop app.

## Workflow

### 1. Propose structure before writing files

If no outline was given, ask once for topic + rough breadth, then sketch the structure in chat for approval. Confirming up front beats regenerating.

### 2. Ensure `xmindmark` is installed

```bash
xmindmark --version || npm install -g xmindmark
```

Requires Node.js. The install lands in the user's npm prefix (no sudo).

### 3. Write the `.xmindmark` source

`xmindmark` writes output to the **current working directory** by default, so `cd` to the target folder first, or use `-o <dir>`. Cyrillic filenames are fine.

Minimal shape:

```
Central Topic

- Branch 1
    * Sub-topic
        - Detail
- Branch 2
    * Sub-topic
```

Indentation: **4 spaces per level** (or one tab). Use `-` or `*` — pick one, stay consistent.

For boundaries, relationships, summaries, marker combinations: read [references/syntax.md](references/syntax.md). Starter file: [assets/template.xmindmark](assets/template.xmindmark).

### 4. Generate

```bash
xmindmark <name>.xmindmark
```

Produces `<name>.xmind` next to the source.

### 5. Verify

```bash
unzip -l <name>.xmind
unzip -p <name>.xmind content.json | python3 -c "import json,sys; d=json.load(sys.stdin); r=d[0]['rootTopic']; print('Root:', r['title']); print('Branches:', [c['title'] for c in r.get('children',{}).get('attached',[])])"
```

Expect `content.json`, `manifest.json`, `metadata.json` in the zip, and the root title + branches printed correctly (Cyrillic renders as-is, not as `\u…` escapes).

### 6. Open in XMind

Linux:

```bash
nohup xmind "<abs-path>.xmind" > /tmp/xmind-open.log 2>&1 & disown
```

macOS: `open -a XMind "<path>.xmind"`. Windows: `start "" "<path>.xmind"`.

The `nohup … & disown` pattern on Linux is required — foreground `xmind` blocks the shell. A 401 line about `xmind.app/_res/user_sub_status` in the log is an unrelated subscription check.

## Quality patterns

What makes a map read well in XMind (apply by default unless the user wants something flatter):

1. **3–4 levels max** — deeper becomes a wall of text in radial layout.
2. **5–9 main branches** — fewer feels sparse, more crowds the canvas.
3. **Parallel structure per level** — same "kind of thing" at each level (all life areas, or all phases). Mixing categories with action items reads as noise.
4. **Boundaries sparingly** — one or two per map, only when grouping isn't obvious from indentation.
5. **Relationships only for genuine cross-references** — meaning the hierarchy can't express.
6. **Summaries for consolidation, not listing** — "given all these → here's the takeaway."
7. **Title case for branches, sentence case for sub-topics** — cues hierarchy without styling.
8. **Short titles** — 2–6 words. Detail belongs at the next level or in a manually-added note.

## Gotchas

- **Generated `.xmind` is minimal** — only `content.json` + `manifest.json` + `metadata.json`. No `content.xml`, no thumbnail. XMind opens it fine and writes a thumbnail on first save.
- **First non-empty line is always the root** — no comments, no preamble.
- **Marker syntax leaves a trailing space in titles** — see syntax.md `## Combining markers`. Cosmetic; do not "fix" by removing the space.

## When `xmindmark` is not enough

For notes (long pane), labels, custom icons, multiple sheets, image attachments, or per-topic styling: use the `xmind-generator` npm package (JS SDK) instead, or generate the skeleton with `xmindmark` and enrich manually in the XMind UI.
