# Browser Upload

## Purpose

Use this reference when writing images into a Lark whiteboard embedded inside a doc page.

## Preflight

- The user must already be logged into Lark in the browser controlled by `bb-browser`.
- The target doc tab should already exist, or you must know the exact doc URL.
- The files to upload should already exist locally.

## Validated UI Assumptions

The current embedded whiteboard flow on this machine exposes:

- board container: `.whiteboard-view-container`
- toolbar more button: `#whiteboard-toolbar-more`
- whiteboard upload entry: `More -> Upload image`
- direct upload input once the more menu is open: `#whiteboard-toolbar-image-sub input[type=file]`
- editable board identity: browser whiteboard requests expose the real `blockToken`

Accepted image types observed in the board UI:

- `image/png`
- `image/jpeg`
- `image/svg+xml`

## Validated Network Signals

Successful upload produced these request families:

- `/space/api/box/upload/prepare/`
- `/space/api/box/upload/blocks/`
- `/space/api/box/stream/upload/merge_block/`
- `/space/api/box/upload/finish/`
- `/space/api/box/file/info/`
- `/space/api/whiteboard/list_resource`
- `/space/api/whiteboard/block?blockToken=...`

If these do not appear, the board was probably not entered correctly or the upload input was not reached.

## Token Notes

- `docs +fetch` may return a document-layer `<whiteboard token="..."/>`, but the board editor itself uses a browser-visible `blockToken`.
- `docs +media-download --type whiteboard --token <blockToken>` returns the correct thumbnail for the editable board.
- Browser upload `upload/finish` returns a `file_token`, and the same token later appears in `whiteboard/list_resource`.

## Current Limitation

- On this machine, `lark-cli docs +whiteboard-update` can append frame/text/link nodes successfully.
- However, image nodes emitted by `@larksuite/whiteboard-cli --to openapi` still return `invalid arg` when sent through `docs +whiteboard-update`, even with a valid uploaded token.
- For now, treat browser upload as the reliable path for image-node creation.

## Failure Patterns

### Another Lark login tab opens

- This usually means the fresh URL was opened outside the already-authenticated tab flow.
- Switch back to the logged-in doc tab and continue there.

### Board click seems to do nothing

- Synthetic DOM click is not enough.
- Use real CDP mouse events.

### Upload finishes but nothing visible appears

- Wait longer and check `whiteboard/list_resource`.
- Confirm you are inside the board editor, not only the outer doc shell.

### Script cannot find the upload input

- The board may still be in the outer doc shell, or the whiteboard more-tools menu has not been opened yet.
- On this machine, the stable browser path is: click `#whiteboard-toolbar-more` -> use the `Upload image` item -> target `#whiteboard-toolbar-image-sub input[type=file]`.
- If Lark changes the DOM again, prefer a selector scoped under `.whiteboard-protal-container` rather than a page-global `input[type=file]`, otherwise you may hit a doc/comment uploader instead of the whiteboard uploader.
