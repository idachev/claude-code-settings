# xmindmark Syntax Reference

Complete syntax for `.xmindmark` source files (xmindmark v0.3.x).

## Table of Contents
- [Root topic](#root-topic)
- [Branches and nesting](#branches-and-nesting)
- [Boundaries `[B]`](#boundaries)
- [Relationships `[N]` / `[^N]`](#relationships)
- [Summaries `[S]`](#summaries)
- [Combining markers](#combining-markers)
- [Indentation rules](#indentation-rules)
- [What is NOT supported](#what-is-not-supported)

## Root topic

The first non-empty line is the central topic. No prefix.

```
My Mind Map
```

## Branches and nesting

Use `-` or `*` followed by one space for branches. Indent with **4 spaces** (or one tab — tab = 4 spaces) for each deeper level. `-` and `*` are interchangeable but stay consistent within a level for readability.

```
My Mind Map

- Branch 1
    * Sub 1.1
        - Sub 1.1.1
            * Sub 1.1.1.1
- Branch 2
```

Blank lines between branches are optional and ignored.

## Boundaries

Group consecutive same-level topics with `[B<n>]`. Define the boundary title with `[B<n>]: Title` on its own line at the same indent level.

```
- Parent
    * Item A [B1]
    * Item B [B1]
    * Item C [B1]
    [B1]: Group Title
```

The `<n>` ties topics to their title. Use `[B1]`, `[B2]`, etc. when you have multiple boundaries on the same parent.

## Relationships

Cross-topic arrow. Mark the source with `[N]` and the target with `[^N](Label)`. The label appears on the arrow.

```
- Topic A [1]
- Topic B [^1](leads to)
```

This draws an arrow from A → B labelled "leads to".

## Summaries

Wrap consecutive topics with `[S<n>]` to produce a summary node. Define the summary topic with `[S<n>]: Title`. Summaries can have their own children (indent under the definition line).

```
- Item 1 [S1]
- Item 2 [S1]
- Item 3 [S1]
[S1]: Combined insight
    - Sub-point of summary
    - Another sub-point
```

## Combining markers

Multiple markers attach directly to a topic with no intervening spaces between markers:

```
- Autumn [B1][^1](Cool)[S1]
```

**Gotcha:** the space between the topic text and the first marker (e.g. `Autumn [B1]`) gets preserved in the resulting title in the generated `.xmind`, leaving a trailing space (title becomes `"Autumn "`). This is harmless visually in XMind, but worth knowing if downstream tooling parses titles strictly. The xmindmark spec requires that space, so it cannot be removed without breaking the marker.

## Indentation rules

- **One level = 4 spaces** (or one tab; tabs are normalized to 4 spaces).
- Mixing tabs and spaces within the same file works but is fragile — pick one and stick with it.
- The root topic itself takes no indent and no bullet.

## What is NOT supported

These features exist in XMind but **cannot** be expressed in xmindmark — they have to be added manually in the XMind UI after generation, or built with the `xmind-generator` JS SDK instead:

- Floating topics (disconnected from root)
- Topic notes (the long-form note pane)
- Labels (the small colored chips on topics)
- Icon/emoji markers (priority flags, task markers, etc.)
- Multiple sheets in one workbook
- Custom topic colors / styling
- Images or attachments on topics

If the user needs any of these, recommend either (a) generate the structure with xmindmark, then enrich in XMind UI, or (b) switch to `xmind-generator` (npm: `xmind-generator`) for full programmatic control.
