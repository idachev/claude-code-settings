# Hashtag Analytics Sources — What Works and What Doesn't

Tested March 2026. Sources are ranked by reliability for WebFetch-based lookups.

## Tier 1: Working Sources (use first)

### best-hashtags.com
- **Works for**: English/Latin hashtags
- **URL pattern**: `https://best-hashtags.com/hashtag/{hashtag}/`
- **Returns**: Full post counts, related hashtags with counts, difficulty ratings
- **WebFetch prompt**: "List all hashtags shown with their popularity or post counts"
- **Limitations**: Does not index Cyrillic hashtags well

### displaypurposes.com
- **Works for**: Popular Cyrillic hashtags shared across large languages (Russian/Bulgarian/Ukrainian)
- **URL pattern**: `https://displaypurposes.com/hashtags/hashtag/{url-encoded-hashtag}`
- **Returns**: Post count for primary hashtag + top 20 related hashtags with counts
- **WebFetch prompt**: "Find the post count for hashtag #{tag} and list all related hashtags with their post counts"
- **Limitations**: Returns 404 for smaller/niche Cyrillic hashtags (e.g., Bulgarian-only words like вдъхновение, промяна, любов). Only works for tags with enough volume (generally 1M+ posts, often shared with Russian).
- **Confirmed working example**: `#мотивация` → 10,947,567 posts

### ritetag.com
- **Works for**: Partial data, mostly English and popular tags
- **URL pattern**: `https://ritetag.com/best-hashtags-for/{hashtag}`
- **Returns**: Hashtag classification (good/great/poor), tweet counts, exposure estimates
- **WebFetch prompt**: "List all hashtags shown with their post counts, popularity scores, or any metrics"
- **Limitations**: Data is Twitter-focused, limited Instagram/TikTok metrics. Cyrillic support is spotty.

## Tier 2: WebSearch Fallback

When Tier 1 sources return no data, use WebSearch queries:

```
Best queries (in order of usefulness):
1. "best hashtags for [topic] [language] instagram tiktok"
2. "#tagname instagram posts count [year]"
3. "най-популярни хаштагове [topic]" (for Bulgarian-specific)
4. "popular [language] hashtags motivation life love instagram"
5. "[hashtag tool site] #tagname posts" (e.g., displaypurposes, iqhashtags)
```

WebSearch often surfaces blog posts and guides that list popular hashtags by category with approximate counts.

## Tier 3: Sources That FAIL (do not waste time)

### tagsfinder.com
- **Status**: Returns HTTP 403 (Forbidden)
- **Do not use via WebFetch**

### iqhashtags.com
- **Status**: JavaScript-rendered SPA — WebFetch returns only framework code (font loaders, analytics scripts), no actual data
- **Do not use via WebFetch**

### Instagram explore/tags pages
- **Status**: Require authentication, return login walls
- **Do not use via WebFetch**

### hashtagmenow.com, top-hashtags.com
- **Status**: Inconsistent results, often return generic lists without counts
- **Low priority**: Only use if all Tier 1 sources fail

## URL Encoding Reference for Cyrillic

When constructing URLs for Cyrillic hashtags, URL-encode the text:

| Bulgarian | URL-encoded |
|-----------|-------------|
| мотивация | %D0%BC%D0%BE%D1%82%D0%B8%D0%B2%D0%B0%D1%86%D0%B8%D1%8F |
| любов | %D0%BB%D1%8E%D0%B1%D0%BE%D0%B2 |
| живот | %D0%B6%D0%B8%D0%B2%D0%BE%D1%82 |
| свобода | %D1%81%D0%B2%D0%BE%D0%B1%D0%BE%D0%B4%D0%B0 |
| вдъхновение | %D0%B2%D0%B4%D1%8A%D1%85%D0%BD%D0%BE%D0%B2%D0%B5%D0%BD%D0%B8%D0%B5 |
| психотерапия | %D0%BF%D1%81%D0%B8%D1%85%D0%BE%D1%82%D0%B5%D1%80%D0%B0%D0%BF%D0%B8%D1%8F |
| промяна | %D0%BF%D1%80%D0%BE%D0%BC%D1%8F%D0%BD%D0%B0 |

Tip: Use `python3 -c "import urllib.parse; print(urllib.parse.quote('hashtag'))"` via Bash to encode any Cyrillic string.

## Estimation Heuristics for Small-Language Hashtags

When analytics tools return no data for a Cyrillic hashtag, estimate its post count:

1. **Is the word shared with Russian?** (e.g., мотивация, свобода, психотерапия)
   - If yes: likely 500K–10M+ posts (Russian Instagram has ~60M users)
   - Try displaypurposes.com first — it often has data for these

2. **Is it Bulgarian/Serbian/etc. only?** (e.g., любов, живот, вдъхновение, промяна)
   - Divide the Russian-equivalent tag's count by 15–25
   - Bulgarian Instagram has ~2-3M active users vs Russia's ~60M
   - Generic concepts (любов/love) → higher end of estimate
   - Niche concepts (промяна/change) → lower end

3. **Popularity tier guide for Bulgarian-only tags:**
   - 200K–500K: Universal concepts (love, life, happiness)
   - 50K–200K: Common themes (inspiration, freedom, change)
   - 10K–50K: Specific topics (running, snow, mountain, psychotherapy)
   - 1K–10K: Very niche (specific locations, compound words like живейпълноценно)
