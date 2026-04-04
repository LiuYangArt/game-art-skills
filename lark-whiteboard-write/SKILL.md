---
name: lark-whiteboard-write
description: Upload selected local images into a Feishu/Lark doc-embedded whiteboard through the user's logged-in browser session. Use when Codex needs to enter a whiteboard inside a doc, place curated reference images on the board, or automate board-side image upload because lark-cli alone is not enough.
---

# Lark Whiteboard Write

## Overview

Use this skill for the board-writing slice only: inspect an embedded Feishu/Lark whiteboard, upload already-curated local images through the logged-in browser session, and use the result as the write primitive for board assembly.

Prefer this skill when the real workflow must happen inside the browser. Do not use it for reference search, prompt writing, or Obsidian canvas generation.

## Workflow

1. Inspect the real board session first.
   - Make sure the user is already logged into Lark in the same browser session that `bb-browser` controls.
   - Make sure the target doc tab is already open, or at least know the target doc URL.
   - Read [references/browser-upload.md](references/browser-upload.md) before first use on a new machine.
   - Run `node scripts/inspect_embedded_board.js --doc-url <doc-url>` to capture the real embedded board `blockToken` and current image/text signals.

2. Prepare the image list.
   - Only upload images that already passed curation.
   - Use local absolute file paths.
   - Prefer small, meaningful batches so verification stays cheap.

3. Run the upload script.
   - Use `node scripts/upload_embedded_board_images.js --doc-url <doc-url> --file <abs-path> ...`
   - If you only need to verify browser reachability and board entry, use `--preflight-only`.
   - The script now returns the real board `blockToken`, upload `file_token`s, and `list_resource` tokens in one JSON payload.
   - On this machine, the stable upload route is through the whiteboard toolbar: `More -> Upload image`. Do not assume the upload input is always mounted before the menu is opened.

4. Verify success before continuing.
   - The board toolbar should appear.
   - The script output should report upload-related requests and `file_token`s.
   - The image should be visibly present on the board at usable size.

5. Treat image placement and DSL placement as two separate primitives.
   - Browser upload is the reliable path for image nodes.
   - `lark-cli docs +whiteboard-update` is reliable for frame/text/link additions.
   - As of current validation on this machine, image nodes produced by `@larksuite/whiteboard-cli --to openapi` still get `invalid arg` from `docs +whiteboard-update`, even when the token is valid. Do not assume DSL image append works.

## Command Pattern

Preflight only:

```bash
node scripts/inspect_embedded_board.js ^
  --doc-url "https://example.larksuite.com/docx/XXX"

node scripts/upload_embedded_board_images.js ^
  --doc-url "https://example.larksuite.com/docx/XXX" ^
  --preflight-only
```

Upload images:

```bash
node scripts/upload_embedded_board_images.js ^
  --doc-url "https://example.larksuite.com/docx/XXX" ^
  --file "E:\\path\\image-01.jpg" ^
  --file "E:\\path\\image-02.png"
```

Useful options:

- `--timeout-ms <n>`: how long to wait for the board UI and upload completion
- `--wait-ms <n>`: extra settle time after file assignment
- `--board-selector <css>`: override board container selector if Lark changes DOM
- `--upload-selector <css>`: override upload input selector if needed

## Rules

- Enter the board first. Do not treat the outer doc shell as the upload surface.
- Prefer the browser path over `lark-cli` for image placement into existing embedded boards.
- Prefer the real browser-observed `blockToken` over the doc markdown `<whiteboard token="..."/>` wrapper token when you need the actual editable board identity or board thumbnail.
- When the direct upload selector misses, open `#whiteboard-toolbar-more` and use the `Upload image` entry scoped under the whiteboard portal, not a page-global file input.
- Use `lark-cli` only for adjacent tasks such as doc discovery or token lookup when needed.
- If opening a fresh URL creates an unexpected login tab, switch back to the already logged-in doc tab instead of assuming the session is gone.
- If a batch upload would obviously pollute the board, stop and shrink the batch first.

## Boundaries

This skill is not for:

- searching references
- evaluating reference quality
- writing Nano Banana prompts
- translating a whole Obsidian canvas layout into a fully arranged Lark board

Use this skill as the write primitive after those upstream decisions are already made.
