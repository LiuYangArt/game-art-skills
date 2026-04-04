# Prompt Library Rules

The prompt library is for reusable blocks, not raw generation history.

## Store Blocks, Not Walls Of Text

Preferred categories:

- `subject`
- `form-language`
- `materials`
- `lighting`
- `camera`
- `whitebox-3d`
- `line-sketch`
- `negative`

Each block should contain:

- a short name
- the prompt text
- when to use it
- optional warnings

## Good Entry Example

```markdown
## whitebox-3d

### hard-surface-massing-clean
- Use when: early volume studies for industrial or sci-fi forms
- Prompt: simplified hard-surface whitebox, clean primary masses, readable major cut lines, minimal small detail, neutral studio lighting, orthographic-friendly presentation
- Notes: good for blocking before material exploration
```

## Bad Entry Example

```markdown
prompt 17:
industrial design thing maybe futuristic and clean but not too clean and maybe white background and some nice detail...
```

Bad entries fail because they are vague, noisy, and hard to reuse.

## Extraction Rules

After each generation round:

1. keep only blocks that clearly helped
2. rewrite them into short reusable form
3. separate reusable prompt logic from project-specific nouns
4. keep one negative block when it generalizes well

## Whitebox And Sketch Focus

The most reusable blocks in early concept work are usually:

- silhouette control
- primary massing language
- material suppression
- clean lighting
- orthographic or semi-orthographic camera cues
- sketch rendering style constraints
