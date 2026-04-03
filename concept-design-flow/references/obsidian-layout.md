# Obsidian Project Layout

Use a stable folder layout so the concept can be resumed without re-reading unrelated notes.

## Recommended Layout

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

## File Purposes

- `00-brief.md`: user-approved problem statement and constraints
- `01-search-plan.md`: search axes, sources, and acceptance criteria
- `02-shortlist.md`: evaluated references and final selected set
- `03-generation.md`: locked direction, generation blocks, and active references
- `04-review.md`: what worked, what failed, next iteration notes
- `05-prompt-library.md`: reusable prompt blocks, not raw logs
- `references.canvas`: visual navigation board
- `assets/`: downloaded or copied local reference files

## Naming Rules

- Use a short project slug in lowercase with hyphens.
- Keep numbered files stable across the project lifetime.
- Avoid renaming files after they are linked into the canvas.

## Canvas Update Rules

- Keep the canvas as a board of pointers and short notes.
- Put long analysis in Markdown notes, then link to it from the canvas.
- Prefer one board per concept project.

## Minimal Resume Read Set

When resuming work, read these files first if they exist:

1. `00-brief.md`
2. `02-shortlist.md`
3. `03-generation.md`
4. `04-review.md`

Only read `01-search-plan.md` or `05-prompt-library.md` if the next action depends on them.
