---
name: hashtag-researcher
description: Research and rank social media hashtag popularity for Instagram, TikTok, and YouTube. Use when the user asks to find hashtags, rank hashtags by popularity, search for best tags for a video/post, or needs hashtag post counts. Handles both Latin and Cyrillic (Bulgarian, Russian, etc.) hashtags. Encodes which analytics websites work via WebFetch and which fail, plus estimation strategies for niche-language tags.
---

# Hashtag Researcher

Research, rank, and select the most popular hashtags for social media content.

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

### Step 5: Update Metadata

Write the selected tags into the user's metadata JSON file, ordered by popularity (most popular first).

## Output Format

Always present results as a ranked table:

```
| Rank | Hashtag      | Posts (est.) | Source    |
|------|------------- |------------- |-----------|
| 1    | #мотивация   | ~10.9M       | confirmed |
| 2    | #свобода     | ~1-3M        | estimated |
| ...  | ...          | ...          | ...       |
```
