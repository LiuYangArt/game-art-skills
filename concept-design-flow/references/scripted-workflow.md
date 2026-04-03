# Scripted Workflow

Use this when the user wants the fast, repeatable path instead of manually re-running every step.

## Roles

- the main model still owns: kickoff discussion, topic-block design, final taste decisions, final Obsidian writes
- scripts own: deterministic search execution, result normalization, asset download, canvas generation, prompt-pack generation, run-state persistence

## File Flow

1. `design-plan.json`
2. `search-results.json`
3. `selected-refs.json`
4. `prompt-pack.json`
5. `references.canvas`
6. `run-state.json`

## Scripts

- `scripts/search_runner.py`
- `scripts/ref_curator.py`
- `scripts/prompt_builder.py`
- `scripts/canvas_builder.py`
- `scripts/run_state.py`

## Preflight

Before running search, confirm `bb-browser` can see a connected browser:

```bash
bb-browser tab list --json
```

If this returns a `Chrome not connected` style error, repair the browser/daemon connection first.

## Recommended Sequence

```bash
python scripts/search_runner.py ^
  --plan design-plan.json ^
  --output search-results.json ^
  --state run-state.json

python scripts/ref_curator.py ^
  --plan design-plan.json ^
  --search-results search-results.json ^
  --output selected-refs.json ^
  --state run-state.json

python scripts/prompt_builder.py ^
  --selected-refs selected-refs.json ^
  --output prompt-pack.json ^
  --state run-state.json

python scripts/canvas_builder.py ^
  --selected-refs selected-refs.json ^
  --prompt-pack prompt-pack.json ^
  --output references.canvas ^
  --state run-state.json
```

## Stability Rules

- do not feed raw `search-results.json` directly into Obsidian Canvas
- only `selected-refs.json` may drive the final board
- keep source priority fixed as `Pinterest > Huaban > Tumblr` unless the user explicitly asks otherwise
- when curating Pinterest results, `ref_curator.py` should batch-fetch pin detail pages and prefer detail-page title/image over search-card thumbnails
- for noisy topics, define hard topic constraints in `design-plan.json`: `must_match`, `reject_match`, and when needed `must_match_groups`
- use `selection.min_score`, `selection.min_must_match_hits`, and `selection.require_all_match_groups` to keep weak results out of the shortlist
- add `selection.require_signal_title` when you want to reject `Selection`, `收藏到 ...`, `stock photo`, and similar low-signal title noise
- hard rejection is preferred over force-filling: `selected_count` may be smaller than `selection.max`, including zero
- only overwrite an existing canvas block when the new batch is clearly more relevant and the images are materially better than the old batch
- if downloads fail, keep the origin URL and error in JSON instead of silently dropping the item
- use `run-state.json` to resume; do not assume a missing board means nothing was done

## Pinterest Detail Enrichment

`ref_curator.py` should treat Pinterest search cards as discovery only. The shortlist should be built from pin-detail data whenever possible:

- fetch each shortlisted pin URL in parallel through `bb-browser`
- extract a better image URL from the detail page, preferring `1200x`, `originals`, then `736x`
- extract detail-page title and description
- score against the enriched title/description, not only the search-card thumbnail metadata
- penalize or reject low-signal titles such as `Oops!`, `Selection`, `收藏到 ...`, generic social reposts, and obvious marketplace noise

## Topic Spec Pattern

Recommended topic shape inside `design-plan.json`:

```json
{
  "id": "hull-openings",
  "title": "通风格栅 / 排水口 / 舷侧开孔",
  "pinterest_query": "warship vent grille scupper hull opening",
  "must_match": ["vent", "grille", "scupper", "opening", "ship", "hull"],
  "reject_match": ["car", "rv", "facebook", "stock photo", "restoration"],
  "must_match_groups": [
    ["vent", "grille", "scupper", "opening", "louver"],
    ["ship", "warship", "navy", "hull", "carrier"]
  ],
  "selection": {
    "max": 3,
    "min_score": 92,
    "min_must_match_hits": 2,
    "require_all_match_groups": true,
    "require_signal_title": true,
    "reject_on_reject_match": true
  }
}
```

This pattern exists to avoid a common failure mode: article covers, interior shots, e-commerce thumbnails, or generic industrial parts scoring high enough to pollute the board.
