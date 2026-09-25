---
name: hashtag-researcher
description: Use when the user asks to find hashtags for a social media post or video, to rank hashtags by popularity, to pick the best tags for a reel, or needs Instagram, TikTok or YouTube post counts for specific tags. Covers Latin and Cyrillic tags, including Bulgarian and Russian ones that most analytics sites do not index.
---

# Hashtag Researcher

Research, rank, and select the most popular hashtags for social media content.

## When not to use

- The user wants caption or copy writing, not tag selection.
- The user wants live engagement analytics for their own account. This skill reads public
  aggregate post counts only; it has no account access.
- The user names one platform's paid analytics product. Use that product, not these sources.

## Workflow

### Step 1: Generate Candidate Hashtags

From the user's content description, generate 15-25 candidate hashtags covering:
- **Core theme** (what the video is about)
- **Emotion/mood** (motivation, love, freedom, etc.)
- **Visual elements** (snow, sun, mountain, running, etc.)
- **Platform trends** (short-form video, reels, etc.)

Ask the user which language(s) to target. This determines the lookup strategy.

### Step 2: Look Up Popularity

Use the tiered source strategy in [references/sources.md](references/sources.md) to fetch post counts.

**Parallel lookup**: Fire WebFetch calls to multiple working sources simultaneously for each hashtag to maximize hits.

**Key rule**: Always URL-encode Cyrillic hashtags for WebFetch URLs. Example: `мотивация` → `%D0%BC%D0%BE%D1%82%D0%B8%D0%B2%D0%B0%D1%86%D0%B8%D1%8F`

### Step 3: Estimate Missing Data

For hashtags where no source returns data (common for small-language Cyrillic tags like Bulgarian-only words), estimate relative popularity using:

1. **Language community ratio**: Bulgarian ~7M speakers vs Russian ~145M (~20x smaller). If a shared-language tag has N posts, a Bulgarian-only equivalent likely has N/15 to N/25 posts.
2. **Topic breadth**: Generic concepts (love, life, motivation) rank higher than specific ones (running, snow, piste).
3. **WebSearch for indirect signals**: Search for `"#tagname" instagram` to find mentions that hint at relative usage.

### Step 4: Rank and Select

1. Rank all candidates by confirmed or estimated post count (descending).
2. Present the full ranked table to the user with counts or estimates.
3. Select the top N tags (user-specified, default 7).
4. Consider mixing popularity tiers: a few high-volume tags for reach + a few niche tags for discoverability.

### Step 5: Write the Tags Back (only when a target file is named)

Skip this step unless the user names a file to update. Never guess a path and never create a
metadata file on your own — the ranked table from Step 4 is the deliverable by default.

When the user does name a JSON file, read it first, then write the selected tags into the field
that already holds them, ordered by popularity (most popular first). Keep the existing key name,
the existing value shape (array of strings, with or without a leading `#`), and the rest of the
file untouched.

If the file has no such field, ask which key to use instead of inventing one.

## Output Format

Always present results as a ranked table:

```
| Rank | Hashtag      | Posts (est.) | Source    |
|------|------------- |------------- |-----------|
| 1    | #мотивация   | ~10.9M       | confirmed |
| 2    | #свобода     | ~1-3M        | estimated |
| ...  | ...          | ...          | ...       |
```
