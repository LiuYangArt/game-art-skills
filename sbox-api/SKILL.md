---
name: sbox-api
description: Use when working with s&box gameplay code, engine API lookup, schema refresh, or when you need to verify whether a Sandbox type/member really exists before writing C# code.
---

# s&box API

Use this skill before writing or reviewing s&box C# gameplay code when API details are uncertain.

## Scope

This skill wraps the existing local tools under `F:\CodeProjects\sbox\tools` and adds one stable skill-side entrypoint:
- `F:\CodeProjects\sbox\tools\update_sbox_schema.py` refreshes the local schema from `https://sbox.game/api/schema`
- `F:\CodeProjects\sbox\tools\sbox_lookup.py` queries the local schema for types, members, and text matches
- `C:\Users\LiuYang\.codex\skills\sbox-api\scripts\run_sbox_api.py` is the preferred thin wrapper for agent calls

Do not rewrite the workspace tools unless the user asked to improve them. Prefer calling them directly through the wrapper.

## Default workflow

1. If the requested API may have changed or no local schema exists, refresh schema first:

```powershell
python C:\Users\LiuYang\.codex\skills\sbox-api\scripts\run_sbox_api.py refresh
```

2. Query the schema before generating code:

```powershell
python C:\Users\LiuYang\.codex\skills\sbox-api\scripts\run_sbox_api.py stats
python C:\Users\LiuYang\.codex\skills\sbox-api\scripts\run_sbox_api.py type Sandbox.Component --members
python C:\Users\LiuYang\.codex\skills\sbox-api\scripts\run_sbox_api.py member OnUpdate
python C:\Users\LiuYang\.codex\skills\sbox-api\scripts\run_sbox_api.py search physics --assembly Sandbox.Engine
```

3. Only after the type/member is confirmed should you write gameplay code.

## Agent-native expectations

- Prefer the wrapper script so future calls use one stable command surface.
- Report the exact command used.
- Report whether schema was refreshed or an existing local schema was used.
- Quote the exact confirmed type/member names that support the conclusion.
- Treat schema presence as existence evidence, not full runtime usage proof.
- For uncertain behavior, follow up by checking engine source, project patterns, or runtime validation.

## Command selection

- Use `type` for exact type confirmation.
- Use `member` for exact method/property/field lookup.
- Use `search` to discover candidate APIs when names are uncertain.
- Use `stats` to confirm the local schema is present and readable.
- Use `refresh` when the local schema may be stale or missing.

## Failure handling

- If wrapper reports missing tools under `F:\CodeProjects\sbox\tools`, stop and surface the error.
- Do not silently fall back to invented API guesses.
- If schema confirms existence but usage is still unclear, say that runtime behavior remains unverified.
