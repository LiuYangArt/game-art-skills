# bb-browser Search Guidance

Use this when `bb-browser` is available and the user is already logged into Pinterest, Tumblr, or other browser-only sources.

## Why Prefer bb-browser

- it reuses the user's real browser session
- it avoids many public-endpoint rate limits and anti-bot issues
- it is better suited to image-heavy sites that do not expose stable APIs

## Current Adapters

Available private adapters on this machine:

- `pinterest/search`
- `huaban/search`
- `tumblr/search`

## Source Roles

### Pinterest

Best for:

- broad reference discovery
- image-first scanning
- finding many variants of the same object or layout

Current adapter return shape:

- `title`
- `url`
- `image`
- `alt`

Use it as the primary image source when you want a larger candidate pool quickly.

### Tumblr

Best for:

- secondary inspiration
- niche communities
- photography and mood references

Current adapter return shape:

- `title`
- `url`
- `blog`
- `tags`

Use it as a supplement, not the only source, because search quality is noisier.

### Huaban

Best for:

- Chinese-language keyword search
- reposted references from local social platforms
- finding mainland-web image variants that do not surface easily on Pinterest

Current adapter return shape:

- `title`
- `url`
- `image`
- `alt`
- `score`

Use it as a supplement, not the only source, because search quality is noisy and often mixed with stock-material content.

## Query Patterns

Do not search only the object name. Split queries by axis.

Good Pinterest examples:

- `aircraft carrier flight deck`
- `carrier island radar`
- `naval ciws deck mount`
- `carrier jet blast deflector`
- `arresting wire flight deck`

Good Huaban examples:

- `航母 甲板`
- `航母 岛式 雷达`
- `航母 近防炮`
- `福建号 航空母舰 甲板`
- `舰载机 起降 甲板`

Good Tumblr examples:

- `aircraft carrier flight deck navy`
- `carrier aviation deck operations`
- `naval radar island warship`

## Search Loop

1. run `pinterest/search` with 2-4 axis-specific queries
2. run `huaban/search` with Chinese keyword variants when you need local-language discovery or ship-name-specific recall
3. keep image-centric candidates with transferable form or device detail
4. run `tumblr/search` only to fill gaps in mood or niche equipment references
5. dedupe near-identical results before presenting a shortlist

## Practical Notes

- Pinterest titles can be sparse or missing; use the image and URL even when the title is weak.
- Huaban can return stock or repost noise; favor results whose title clearly mentions the target object or equipment.
- Tumblr tags often carry more signal than the title.
- Do final taste judgment in the main agent, not inside the adapter output.
