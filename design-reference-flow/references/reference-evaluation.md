# Reference Evaluation Rubric

Use this rubric to decide whether a reference image is actually useful for concept design rather than merely attractive.

Score each dimension from `1-5` and add one short note.

## Dimensions

### 1. Brief Fit

- `5`: directly supports the current concept goal
- `3`: partially relevant but needs interpretation
- `1`: visually interesting but mismatched to the brief

### 2. Transferable Form Language

- `5`: clearly teaches silhouette, proportion, or structural decisions
- `3`: some form cues are useful, but the image is noisy
- `1`: mostly surface polish with weak form guidance

### 3. Material Or Surface Value

- `5`: gives concrete surface, finish, or fabrication cues
- `3`: broad mood value but vague material detail
- `1`: material treatment is unclear or misleading

### 4. Composition Or Camera Value

- `5`: useful framing or presentation logic for the target deliverable
- `3`: composition is decent but not central to the task
- `1`: dramatic composition that does not help production decisions

### 5. Generatability

- `5`: can be translated into prompt guidance or design constraints
- `3`: useful inspiration but requires heavy interpretation
- `1`: too post-processed, too bespoke, or too dependent on hidden craft

### 6. Uniqueness In The Set

- `5`: adds a distinct insight not covered by other candidates
- `3`: overlaps with existing references but still adds some value
- `1`: near-duplicate of stronger candidates

## Quick Reject Rules

Reject or demote candidates that are:

- beautiful but unrelated to the brief
- duplicated in silhouette, lighting, and mood
- only useful because of rendering tricks
- impossible to translate into practical design guidance
- so stylized that they obscure real form decisions

## Synthesis Rules

- A shortlist should usually cover complementary strengths, not identical tastes.
- It is acceptable for one image to win on form while another wins on materials.
- Explain why a weaker but more transferable reference may beat a prettier one.

## Model Strategy

Default to the main model for final scoring and synthesis.

Use smaller models or mini subagents only for coarse pre-filtering when:

- the pool is large enough to justify batching
- the user explicitly asked for speed or parallel work
- the final taste judgment remains with the main agent
