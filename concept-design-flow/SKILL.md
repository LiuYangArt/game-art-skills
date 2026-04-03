---
name: concept-design-flow
description: Use when a user wants guided concept design work with staged approvals, reference-image curation, Obsidian notes or canvas boards, reusable prompt libraries, or iterative image generation grounded in selected references.
---

# Concept Design Flow

## Overview

Run concept design as a gated workflow rather than a one-shot prompt. This skill is for concept art, product form exploration, moodboards, key visual direction, 3D whitebox refinement, line-sketch refinement, and similar visual discovery work where the user should approve each stage before moving forward.

This skill assumes Obsidian is the project memory layer. Use existing Obsidian capabilities to read, search, create, and update `.md` and `.canvas` files directly instead of recursively scanning the whole vault.

When the user wants speed, repeatability, or resumable execution, prefer the scripted fast path documented in [references/scripted-workflow.md](references/scripted-workflow.md).

The default working shape is:

1. discuss the concept goal and style
2. break the object into usable design categories
3. turn categories into keyword packs
4. search references in parallel
5. merge results into topic blocks on the canvas
6. derive reusable generation prompts from the approved topic blocks

For fast concept-board work, the preferred path is a single up-front discussion that surfaces the likely categories, useful reference targets, search goals, and style anchors before any browsing starts.

## External Requirements

Keep this skill folder intact when sharing it. `SKILL.md` depends on the sibling `assets/`, `references/`, `scripts/`, and `agents/` directories through relative links and script paths.

Hard runtime dependencies:

- Obsidian access capable of reading and writing `.md` and `.canvas` files. `obsidian-cli` is the expected setup.
- `bb-browser` with a connected browser session for Pinterest, Huaban, and Tumblr search.
- Python 3.11+ to run the helper scripts in `scripts/`.

Soft dependencies:

- `$brainstorming` is referenced as an interaction style, not a hard runtime requirement.
- Subagents are optional and only used when the user explicitly asks for parallel search.
- Nano Banana prompt output is supported, but the skill can still be used for reference curation without image generation.

## Core Rules

- Ask one clarifying question at a time during briefing. Reuse the interaction style of `$brainstorming`: prefer 2-3 concrete choices with plain-language impact.
- Add a confirmation gate after each major stage: brief, search plan, shortlist, direction lock, generation review, prompt-library update.
- Keep ownership in the main agent for: final brief synthesis, final shortlist, all Obsidian writes, generation-direction decisions, and final recommendations.
- Default to single-agent execution. Use `subagent` parallelization only when the user explicitly asks for speed, delegation, or parallel work.
- When the user explicitly asks for speed or parallel search, switch to a fast kickoff flow: discuss the concept once, enumerate likely reference targets and keyword packs up front, ask for one consolidated confirmation, then launch parallel search instead of forcing stage-by-stage micro-confirmations.
- After that kickoff confirmation, do not pause between every topic block unless the user explicitly asks to inspect an intermediate batch.
- Do not jump to image generation before at least one visual direction is locked.
- Favor simple storage: Markdown notes plus one `.canvas` board per concept.
- Prefer precise `obsidian read/search/open` access. Do not full-scan the vault unless the user explicitly asks.
- When the user is working with Nano Banana or Gemini image editing, default prompt writing to Chinese unless the user explicitly asks for another language.
- When the user asks for continuation-friendly browsing, store Pinterest search links on the canvas as compact text nodes rather than noisy preview cards.
- When the user asks for generation-ready handoff, persist a compact Nano Banana prompt pack on the canvas in addition to any Markdown notes.
- Do not treat raw keywords as the final canvas output. The final canvas should be organized as topic blocks, with each block pairing a small image cluster, a relevant search link, and a short design-use note.
- For reference curation, prefer `must_match`, `reject_match`, and `must_match_groups` over loose semantic guesses. Noisy topics should be allowed to return fewer than the requested count, including zero.
- Only replace an existing canvas image cluster when the new batch is clearly better: larger image, tighter topic match, and more usable design information.
- For repeatable execution, store intermediate artifacts as JSON files instead of keeping state only in the conversation.

## When To Use

Use this skill when the user wants any of the following:

- Turn a vague concept into a structured design brief.
- Search and curate reference images before generating.
- Store concept work in Obsidian notes and a canvas board.
- Build a reusable prompt library for later whitebox, sketch, or refinement work.
- Re-open an existing concept-design project and continue from the saved state.

Do not use this skill when the user only wants a single image immediately and clearly does not want structured reference work or documentation.

## Workflow Decision Tree

Choose the narrowest entry point that fits the request:

1. **New concept project**
   - No saved project exists yet, or the user wants a fresh branch of exploration.
   - Start at Stage 1 and create the project files.

2. **Continue an existing concept**
   - The user already has a note folder or canvas board.
   - Read only the relevant project files, summarize current state, then resume from the first incomplete stage.

3. **Reference curation only**
   - The user already knows the concept but needs better references and a shortlist.
   - Start at Stage 2 or Stage 3.

4. **Generation and refinement only**
   - Brief and references already exist.
   - Verify the locked direction, then start at Stage 5.

5. **Prompt-library maintenance**
   - The user wants to consolidate reusable prompt blocks from past work.
   - Start at Stage 6.

## Project Layout

Read [references/obsidian-layout.md](references/obsidian-layout.md) before creating files.

Recommended project structure:

```text
Concept Design/<project-slug>/
  00-brief.md
  01-search-plan.md
  02-shortlist.md
  03-generation.md
  04-review.md
  05-prompt-library.md
  references.canvas
  assets/
```

If the user already has a preferred Obsidian folder, use it. Otherwise create the structure above and keep file names stable so the project can be resumed later.

Use these templates when creating new files:

- [assets/brief-template.md](assets/brief-template.md)
- [assets/shortlist-template.md](assets/shortlist-template.md)
- [assets/generation-template.md](assets/generation-template.md)
- [assets/review-template.md](assets/review-template.md)
- [assets/prompt-library-template.md](assets/prompt-library-template.md)
- [assets/references-board.canvas](assets/references-board.canvas)
- [assets/design-plan.template.json](assets/design-plan.template.json)
- [assets/selected-refs.template.json](assets/selected-refs.template.json)
- [assets/prompt-pack.template.json](assets/prompt-pack.template.json)
- [assets/run-state.template.json](assets/run-state.template.json)

## Scripted Fast Path

Read [references/scripted-workflow.md](references/scripted-workflow.md) before using the script-assisted path.

Use the scripted path when the user wants:

- faster repeated execution
- stable source priority enforcement
- resumable work across turns
- deterministic canvas generation
- a reusable prompt pack for Nano Banana
- stricter topic-level filtering that keeps bad references out of the canvas

Available scripts:

- `scripts/search_runner.py`
- `scripts/ref_curator.py`
- `scripts/prompt_builder.py`
- `scripts/canvas_builder.py`
- `scripts/run_state.py`

Recommended file flow:

1. `design-plan.json`
2. `search-results.json`
3. `selected-refs.json`
4. `prompt-pack.json`
5. `references.canvas`
6. `run-state.json`

The model should still own the kickoff discussion, topic-block design, final shortlist judgment, and final recommendations. The scripts are there to make execution stable, not to replace design judgment.

When defining a scripted plan for noisy visual topics, prefer this shape:

- `must_match`: loose token pool used both for scoring and for readable debugging.
- `reject_match`: explicit pollution tokens that should normally hard-reject a candidate.
- `must_match_groups`: 2-3 semantic buckets that all need at least one hit, for example `ship-domain` plus `target-part`.
- `selection.min_score`: floor score for shortlist admission.
- `selection.min_must_match_hits`: minimum number of useful topic tokens that must appear.
- `selection.require_signal_title`: reject entries whose visible titles are still dominated by `Selection`, `收藏到 ...`, `stock photo`, and similar low-signal noise.
- `selection.require_all_match_groups`: usually `true` for ship parts, hard-surface details, weapons, and other noisy engineering topics.

The default bias is conservative: a topic block may end up with `selected_count = 0`, and that is preferable to writing weak or off-topic images into Obsidian.

## Stage 1: Briefing And Intake

The goal of this stage is a usable design brief, not a polished prompt.

Ask one question at a time until these fields are stable enough to write down:

- `project goal`
- `deliverable type`
- `target fidelity`
- `must keep`
- `must avoid`
- `design axis candidates`
- `deadline or speed preference`
- `what kind of references count as valid`

Good question types:

- Which output matters most right now: `moodboard`, `single hero concept`, or `exploration set`?
- Should the first round optimize for `speed`, `variety`, or `finish quality`?
- Which constraint is hard: `shape language`, `material`, or `camera/composition`?

### Fast Kickoff Mode

If the user explicitly asks for speed, parallel search, or wants to avoid round-by-round prompting, do not drag Stage 1 and Stage 2 into separate back-and-forth loops.

Instead, produce one kickoff bundle that includes:

- brief summary
- style target
- likely reference targets
- object breakdown or component taxonomy
- search goals by category
- search axes
- keyword packs by axis
- source priority
- what should be rejected early

For concept-design search work, `likely reference targets` should be concrete and visual, for example:

- deck layout and markings
- launch and recovery hardware
- island superstructure
- radar mast and sensors
- deck-edge weapons
- support equipment

For object-heavy design work, the kickoff should also produce a practical category breakdown before keywording. Examples:

- for a carrier: deck layout, launch hardware, island massing, radar and sensors, deck-edge weapons, support equipment
- for a vehicle: body shell, wheel area, intake and exhaust, cockpit, undercarriage, surface breakup, lighting units
- for a product: overall form, seams and parting lines, controls, materials, mounting logic, manufacturing details

After the breakdown, convert each category into a search-ready topic spec instead of a raw keyword list. A good topic spec usually contains:

- the design question this block needs to answer
- 1 pinned Pinterest query for continuation browsing
- `must_match` and `reject_match`
- when precision matters, `must_match_groups`
- selection rules such as `min_score` or `min_must_match_hits`

The kickoff bundle should end with one consolidated confirmation question such as:

- `Use this keyword map and launch search now, or change any target first?`

When the brief is coherent enough:

1. Create or update `00-brief.md`.
2. Summarize the concept in plain language.
3. End with a single confirmation question:
   - `Is this brief locked enough to start reference search?`

Do not continue until the user confirms or explicitly asks to proceed.

## Stage 2: Breakdown And Search Plan

Before searching, split the visual problem into categories that are actually useful for design decisions. Start with object breakdown first, then assign search axes if needed.

For many physical design tasks, the category breakdown is more important than abstract style axes. Ask:

- what are the major parts
- what are the important subassemblies
- what details affect believability
- what details affect later modeling or image generation

Good default axes after the breakdown:

- form and silhouette
- material and surface treatment
- lighting and mood
- composition and camera
- era, genre, or brand language

Write a compact search plan into `01-search-plan.md`:

- category breakdown
- search axes
- source list
- candidate keywords per axis
- concrete reference targets per axis
- what makes a result useful
- what makes a result misleading

When the user asked for speed, do this as one front-loaded keyword map instead of staging it across multiple turns.

For each category or topic block, enumerate:

- `target`
- `why it matters`
- `primary keywords`
- `backup keywords`
- `best source`
- `expected reference types`

Use multiple sources when possible. Avoid gathering ten near-duplicate images from one board.

The key rule is:

- categories first
- keywords second
- search results third

Do not skip straight from user brief to a flat keyword dump.

End with one confirmation question:
- `Use this search plan, or adjust the axes first?`

## Stage 3: Reference Discovery

Use browser or search skills that are already available in the environment. If live search is not available, ask the user for seed links or images instead of pretending that results were found.

When `bb-browser` is installed and the user is already logged into visual platforms, prefer it for reference search because it can reuse the user's real browser session instead of relying on brittle public image endpoints.

Read [references/bb-browser-search.md](references/bb-browser-search.md) before searching with Pinterest, Huaban, or Tumblr.
If using the scripted path, also verify `bb-browser tab list --json` succeeds before launching `scripts/search_runner.py`.

When the user has already approved a kickoff keyword map, execute the searches in batches rather than pausing after every small sub-step.

Once the kickoff is approved, the search loop should be:

1. launch parallel discovery by topic block
2. filter obvious mismatches quickly
3. merge the matched references into topic blocks
4. show the user the organized board rather than raw search logs

For scripted execution, write the kickoff result into `design-plan.json` first, then let `scripts/search_runner.py` generate `search-results.json`.

For each candidate reference, capture at least:

- source URL
- source type
- short why-it-fits note
- short risk note
- optional tags for axis coverage

During collection, prefer breadth over premature narrowing. Gather enough diversity to compare shape, material, and mood separately.

The working unit for collection should usually be a `topic block`, not an entire giant category. Example:

- `deck overall layout and markings`
- `jet blast deflector mechanism`
- `arresting area and recovery zone`
- `island massing and stepped platforms`
- `mast and antenna hierarchy`
- `Phalanx mount and base relation`

Recommended source priority for visual reference work:

1. `Pinterest` via `bb-browser site pinterest/search` for broad image discovery
2. `Huaban` via `bb-browser site huaban/search` for Chinese-language keywords, reposted visual references, and mainland-web discovery
3. `Tumblr` via `bb-browser site tumblr/search` for secondary inspiration and niche image posts
4. Other live browser search sources when the first three do not cover the needed axis

Treat Huaban and Tumblr as supplement sources, not replacements for Pinterest. Huaban is useful when Chinese terms, ship names, or reposted forum/social images matter, but it is noisier and more stock-material-heavy. Tumblr is useful for mood, photography, or niche communities, but its search results are also noisier and more likely to mix in unrelated fandom or text-heavy content.

### Parallel Search With Subagents

Only use `subagent` when all of these are true:

- the user explicitly asked for parallelization, delegation, or speed
- the environment supports subagents
- the task can be split into independent search or evaluation slices

When the above conditions are met, prefer parallel search immediately after the kickoff confirmation instead of waiting for another round.

Recommended fast split for concept reference work:

1. **By axis**
   - Agent A: deck layout and operational surface
   - Agent B: island, mast, radar, and sensors
   - Agent C: launch, recovery, and deck-edge weapons

2. **By source**
   - Agent A: Pinterest primary pass
   - Agent B: Huaban Chinese-language pass
   - Agent C: secondary source cleanup only if needed

Good split strategies:

1. **By source**
   - Agent A: Pinterest
   - Agent B: Behance
   - Agent C: ArtStation or other relevant source

2. **By axis**
   - Agent A: form and silhouette
   - Agent B: material and surface
   - Agent C: lighting and mood

3. **By batch**
   - Agent A: candidates 1-10
   - Agent B: candidates 11-20

Subagents should return only:

- topic block name
- Pinterest search link
- top candidates for that block
- why each candidate is useful
- what should be rejected
- unresolved questions

Whenever possible, each topic-block return should already be strong enough to support a final canvas cluster with `2-3` matched images, `1` Pinterest continuation link, and `1` short design-use note.

The main agent must always do the final merge, dedupe, and presentation. Do not let subagents write into Obsidian or make final taste decisions.

If live search tools share one browser context and parallel execution would cause collisions, still keep the workflow batched: let subagents own keyword generation, prefiltering, or source-specific review while the main agent serializes the fragile browser commands.

## Stage 4: Reference Evaluation And Shortlist

Read [references/reference-evaluation.md](references/reference-evaluation.md).

Evaluate candidates using a consistent rubric. Default to the main model for scoring and synthesis.

Use a smaller model or mini subagents only for coarse pre-filtering when the candidate pool is large enough that direct review would be wasteful. Practical rule:

- `<= 15` candidates: main agent evaluates directly
- `16-40` candidates: optional batch evaluation with mini subagents if the user asked for speed
- `> 40` candidates: coarse pre-filter first, then final scoring by the main agent

Reject references that are beautiful but not transferable. Common failure cases:

- style mismatch with the brief
- impressive rendering that does not help form decisions
- near-duplicates that add no new information
- images with too much post-production trickery to guide generation

Write the evaluated shortlist to `02-shortlist.md` and update `references.canvas`.

Prefer grouping shortlisted references by topic block rather than presenting one flat list. The user should be able to tell which images support which design decision.

When using the scripted path, prefer `scripts/ref_curator.py` to produce `selected-refs.json`, then build the final board from that curated file instead of from raw search output.

The shortlist should usually contain `3-7` references with complementary value, not ten copies of the same answer.

End with one confirmation question:
- `Lock this shortlist, or swap any references before synthesis?`

## Stage 5: Direction Lock

Turn the approved shortlist into a generation-ready direction pack.

If the user wants a deeper style breakdown, use `$design-dna` on the approved shortlist before writing the final direction.

At minimum, extract these blocks:

- `form language`
- `silhouette and proportions`
- `materials`
- `lighting and mood`
- `composition and camera`
- `rendering style`
- `whitebox-3d block`
- `line-sketch block`
- `negative block`

Write the pack to `03-generation.md`.

If the target generator is Nano Banana, also extract a prompt structure that is ready for image-to-image editing:

- `must preserve`
- `subject conversion`
- `materials and texture`
- `lighting and color grading`
- `camera and framing`
- `detail targets`
- `negative constraints`

For Nano Banana image-to-image work, be explicit about what must stay fixed from the input image, especially:

- silhouette
- layout
- proportions
- camera angle
- island position
- deck lanes
- locked equipment placement

Do not write vague Nano Banana prompts such as `make it more realistic`. Spell out the preservation rules and the target finish.

End with one confirmation question:
- `Is this direction locked enough to generate from?`

## Stage 6: Image Generation

Use the user's preferred image-generation skill or tool. This skill does not replace the generation system; it prepares and documents the work around it.

Recommended pattern:

1. **Exploration round**
   - Generate `3-6` variants across clearly different branches.
   - Optimize for direction-finding, not polish.

2. **Selection**
   - Ask the user to choose one branch or combine two branches.

3. **Refinement round**
   - Refine only the selected branch.
   - Tighten prompt blocks and preserve the locked direction.

If the generator is Nano Banana, prefer reusable image-to-image prompt variants such as:

1. `sketch-to-image`
2. `whitebox-to-image`
3. `detail-refinement`

These variants should usually be written in Chinese and should be directly reusable without requiring the user to translate or rewrite them.

Always persist:

- the prompt used
- major parameter choices
- which references were active
- what changed between rounds
- why the user selected or rejected a variant

Do not store only the final image and lose the reasoning.

## Stage 7: Review And Prompt Library

Read [references/prompt-library.md](references/prompt-library.md).

After a generation round, update both:

- `04-review.md` for what worked and failed
- `05-prompt-library.md` for reusable prompt blocks

Store reusable prompt blocks by category:

- `subject`
- `form-language`
- `materials`
- `lighting`
- `camera`
- `whitebox-3d`
- `line-sketch`
- `negative`

When Nano Banana is part of the workflow, also store:

- `must preserve`
- `camera lock`
- `detail-refinement`
- `surface realism`
- `deck-equipment realism`

Only save blocks that are likely to be reused. Do not dump raw, noisy, one-off prompts into the library without cleanup.

End with one confirmation question:
- `Save these prompt blocks into the library as-is, or trim them first?`

## Obsidian Canvas Guidance

Use `$json-canvas` when you need to create or update `references.canvas`.

When a deterministic board is more important than manual one-off tweaking, prefer `scripts/canvas_builder.py` and treat `selected-refs.json` as the only allowed canvas input.

Recommended node types:

- `group` nodes for stages such as `Brief`, `Candidates`, `Selected`, `Rejected`, `Prompt Blocks`
- `file` nodes for local downloaded references and key notes
- `link` nodes for source URLs
- `text` nodes for short concept-relevant comments, rejection reasons, and synthesis notes

Keep the board readable. The canvas is for navigation and comparison, not for storing full essays that belong in Markdown notes.

Canvas hygiene rules:

- keep top-level `nodes` and `edges` arrays present
- use vault-relative paths for `file` nodes
- regenerate node IDs if you duplicate template blocks
- keep long reasoning in Markdown notes, then link from the canvas
- do not add process or admin notes such as source-priority summaries, search logs, round summaries, workflow reminders, or `this round` explanations unless the user explicitly asks for them on the canvas
- only place text notes on the canvas when they directly support visual comparison, form analysis, equipment analysis, rejection decisions, or generation direction
- if provenance, search strategy, or workflow trace matters, store it in Markdown notes rather than the reference canvas
- when the user wants browsing shortcuts, attach the Pinterest search link to a specific topic block rather than dumping many loose links for the whole group
- the preferred pattern is:
  - `2-3` relevant reference images
  - `1` Pinterest link text node for that mini-topic
  - `1` short note explaining what the block is useful for
- do not use noisy Pinterest preview cards or many scattered single-link nodes when one topic block is easier to scan
- do not keep links on the canvas if they are not backed by matching reference images for that same mini-topic
- do not keep image-only clusters without a matching continuation link when the user explicitly asked for browsing shortcuts
- do not let internal keyword lists become canvas content; they belong in notes or in the search plan, not on the final board
- when the user is preparing for Nano Banana generation, add a compact prompt pack area on the canvas with:
  - style summary
  - Nano Banana prompt-writing rules
  - sketch-to-image prompt
  - whitebox-to-image prompt
  - detail-refinement prompt
  - reusable prompt blocks
- default those Nano Banana prompt nodes to Chinese unless the user asked for another language

When the user wants a reusable Chinese Nano Banana handoff, prefer `scripts/prompt_builder.py` to generate `prompt-pack.json`, then render that pack onto the canvas.

## Resume Rules

When continuing an existing project:

1. Read only the known project files.
2. Identify the last confirmed stage.
3. Summarize current status in a few lines.
4. Resume from the earliest stage that is still unstable.

Do not re-run reference search or overwrite prompt libraries if the current state is already approved.

## Output Expectations

A good run of this skill should leave the user with:

- a clear brief
- a documented search plan
- a justified shortlist of references
- a readable Obsidian canvas board
- a generation-ready direction pack
- a reusable prompt library
- Pinterest continuation links when the user asked for self-serve browsing
- Nano Banana-ready Chinese image-to-image prompts when the user is using that model
- topic-block reference clusters where each link is paired with matching images and a short design note
- optional JSON artifacts that allow the whole flow to be resumed without restarting from search

If any stage is skipped, say so explicitly and explain why.
