# Lark Whiteboard Write Plan

## Goal

Stabilize the whiteboard-writing slice for embedded Lark boards so the workflow can:

1. detect the real editable board token
2. upload curated local images through the logged-in browser
3. use the result for downstream board assembly

## Current Working Path

1. Inspect the embedded board through browser CDP.
   - Script: `scripts/inspect_embedded_board.js`
   - Output: real `blockToken`, current preview URLs, image tokens, text snippets

2. Upload images through the embedded board UI.
   - Script: `scripts/upload_embedded_board_images.js`
   - Output: `blockToken`, upload `file_token`, `list_resource` tokens

3. Add non-image board elements through `lark-cli docs +whiteboard-update`.
   - Reliable for: frame, text, hyperlink-style text content

## Important Technical Findings

- The document-layer `<whiteboard token="..."/>` is not always the same token used by the embedded editor.
- The editable board identity on this machine is the browser-observed `blockToken`.
- `docs +media-download --type whiteboard --token <blockToken>` returns the correct board thumbnail.
- Browser upload `upload/finish` returns a `file_token`, and the same token later appears in `whiteboard/list_resource`.

## Current Limitation

- `@larksuite/whiteboard-cli --to openapi` can emit image nodes.
- But sending those image nodes through `lark-cli docs +whiteboard-update` currently returns `invalid arg`.
- Result: image-node creation should use browser upload for now.

## Recommended Assembly Strategy

1. Use browser upload to create image nodes.
2. Use whiteboard DSL only for text/frame/link layers.
3. Do not assume full board parity can be achieved by DSL alone until image-node append is proven.
