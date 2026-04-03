---
name: yunwu-image-gen
description: Generate images with the Yunwu API and save them as local files. Use when the user asks to create an AI image, concept art, reference image, or says phrases like "生成图片", "文生图", or "generate image", optionally with a resolution, aspect ratio, or output path.
---

# Yunwu Image Gen

## Overview

Generate one image from a text prompt through Yunwu and save it to disk.
Read all provider settings from `config.local.json` in this skill directory. Do not use environment variables for this skill.

## Workflow

### 1. Extract parameters

Extract these fields from the user request:

- `prompt`: required
- `resolution`: optional, default to `1K`
- `ratio`: optional, default to `1:1`
- `output`: optional file path or directory path

Use these parsing rules:

- If the user omits `resolution`, use `1K`.
- If the user omits `ratio`, use `1:1`.
- If the user omits `output`, save to `<current working directory>/images/`.
- If the user provides a relative output path, resolve it against the current working directory.
- If the output path ends with an image extension such as `.png`, `.jpg`, `.jpeg`, or `.webp`, treat it as a file path.
- Otherwise treat the output path as a directory.

Interpret common Chinese request forms directly, for example:

- `生成图片：赛博朋克街道`
- `生成图片：赛博朋克街道 分辨率 2K ratio 16:9`
- `生成图片：赛博朋克街道 保存到 outputs\\covers`
- `生成图片：白猫头像 输出到 images\\cat.png`

### 2. Load configuration

Read `config.local.json` from this skill directory. Require these keys:

- `apiKey`
- `baseUrl`
- `model`

If the file is missing or any field is empty, stop and tell the user to edit:

`C:\Users\LiuYang\.agents\skills\yunwu-image-gen\config.local.json`

### 3. Run the script

Prefer running the bundled script instead of reimplementing the HTTP request manually.

Use this command shape:

```powershell
python "C:\Users\LiuYang\.agents\skills\yunwu-image-gen\scripts\generate_image.py" `
  --prompt "<prompt>" `
  --resolution "<1K|2K|4K>" `
  --ratio "<aspect-ratio>" `
  --cwd "<current working directory>" `
  [--output "<relative-or-absolute-path>"]
```

Notes:

- Keep the shell working directory at the user's current project when possible.
- Pass `--cwd` explicitly when there is any doubt about the shell working directory.
- The script creates parent directories automatically.
- The script saves the returned image using the provider mime type when possible and falls back to `.png`.

### 4. Report the result

After the script succeeds:

- Return the final saved file path.
- Mention the effective resolution and ratio if that helps clarify defaults.

If the script fails:

- Surface the concise error message.
- If the failure is caused by missing config, point the user to `config.local.json`.
