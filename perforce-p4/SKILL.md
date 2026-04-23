---
name: perforce-p4
description: Use when working against Perforce Helix Core through the p4 CLI, including first-time local setup or "p4-init" onboarding, workspace inspection, stream discovery, changelists, stream or branch merges, resolves, and conflict-heavy depot operations that should use a local JSON connection profile or a user-supplied onboarding document.
---

# Perforce P4

## Overview

This skill supports two modes:

- `p4-init`: machine bootstrap for a new Perforce setup
- day-2 operations: direct `p4` usage through the checked-in wrapper after setup is complete

The init flow is documented in [references/init-and-onboarding.md](references/init-and-onboarding.md).
The normal command wrapper is [scripts/Invoke-P4.ps1](scripts/Invoke-P4.ps1).
The checked-in PowerShell scripts are thin Windows launchers; the durable command logic lives in Python.

## Configuration Boundaries

Use [config/p4-init.defaults.json](config/p4-init.defaults.json) only for generic shared defaults such as:

- install package id
- recommended local root base paths
- workspace naming patterns

Do not put project-specific depot names, stream mappings, role mappings, or real server addresses in repo-shared defaults.
Those belong in a user-supplied onboarding document or in the current conversation.

Use [config/p4-connection.json](config/p4-connection.json) only for the local machine. It is ignored by git.
Keep only connection data there: `server`, `user`, and optional saved `password`.
Do not ask the user to fill `client` or `charset` in that file.

## Init And Onboarding

When the user says `p4-init`, "初始化 p4", "新人安装 p4", or asks to set up a local workspace from scratch:

1. If the user supplied an onboarding doc path or link, read it first.
2. Then read [references/init-and-onboarding.md](references/init-and-onboarding.md).
3. Extract fixed information from the doc and generic defaults.
4. Resolve connection inputs in this order:
   - explicit user input in the current prompt
   - onboarding doc
   - existing local [config/p4-connection.json](config/p4-connection.json)
5. Verify the live server before making charset decisions:
   - for `ssl:` servers, inspect trust first
   - run real `p4 info` and `p4 counter unicode` checks against the target server
   - if the current client environment fails, compare that with an explicit `-C none` probe to distinguish a non-Unicode server from a bad local `P4CHARSET`
6. Distinguish verified server facts from local creation choices:
   - verified server facts must come from live `p4` calls, such as trust state, `counter unicode`, stream existence, and existing client specs
   - local workspace names and local root paths may be derived from user-confirmed paths, team naming rules, existing client naming patterns, `P4CLIENT`, or host naming defaults when creating a new workspace
   - when you derive a local workspace name or root, say explicitly that it is the local value you are choosing for creation, not a server fact
7. Ask only for missing or sensitive values:
   - server when neither the prompt, onboarding doc, nor local connection config provides it
   - username when neither the prompt nor local connection config provides it
   - password when no saved password or valid ticket is available
   - project stream
   - engine stream when needed
   - local roots when no confirmed base path, onboarding rule, or existing local pattern provides one
   - workspace names when no user override, existing naming rule, or visible local naming pattern provides one
8. If the target stream is unknown, inspect the onboarding doc or list streams with real `p4` commands before asking the user to choose. Do not invent one.
9. Prefer `p4 login` ticket flow. Do not persist the password unless the user explicitly asks.
10. Run [scripts/p4-init.ps1](scripts/p4-init.ps1) to execute install, trust check, live charset verification, login, workspace creation, optional sync, and optional local config generation.
11. After the workspace is created, default to asking the user whether they want to continue syncing in P4V. For large workspaces, prefer P4V over command-line `p4 sync`.
12. Only pass `-Sync` when the user explicitly asked for command-line sync.

Example:

```powershell
pwsh -File .\skills\perforce-p4\scripts\p4-init.ps1 -Server perforce.example:1666 -User liuyang -ProjectStream //streams/dev -WriteConnectionConfig
```

Use `-WhatIf` for a dry run preview.

If the user explicitly wants CLI sync:

```powershell
pwsh -File .\skills\perforce-p4\scripts\p4-init.ps1 -Server perforce.example:1666 -User liuyang -ProjectStream //streams/dev -Sync
```

If the stream is unknown, list it first with a real server call:

```powershell
p4 -p perforce.example:1666 -u liuyang streams
```

## Day-2 Command Entry Point

Use the wrapper instead of raw `p4` when possible:

```powershell
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 info
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 streams
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 client -o
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 opened
```

`Invoke-P4.ps1` works with either:

- a local password stored in `config/p4-connection.json`
- or an existing `p4 login` ticket when `password` is blank

Workspace should come from the active `p4` environment, such as the current working directory, `P4CONFIG`, `P4CLIENT`, or machine-level `p4 set` values. Charset must be validated live per server during onboarding; do not assume an older server state still holds.

## Official Command Reference

For unfamiliar commands, flags, or edge-case behavior:

1. Start with local help: `p4 help <command>`
2. Then read [references/official-docs.md](references/official-docs.md)
3. Prefer the official command page over memory when the task involves complex merge, integrate, stream, branch, or resolve semantics

## Merge And Resolve

For branch or stream merges, conflict handling, or submit preparation, read [references/merge-and-resolve.md](references/merge-and-resolve.md) and follow that workflow.

## Guardrails

- Prefer existing branch specs, stream specs, and workspace mappings over inventing new depot paths.
- Do not submit automatically unless the user asked for the submit.
- Avoid printing secrets back to the user.
- If the server uses `ssl:`, check trust explicitly before login or workspace creation. Do not guess the trust decision.
- Do not assume a server is Unicode-enabled or non-Unicode from memory, old docs, or prior sessions. Verify it live with real `p4` commands before choosing a charset path.
- If the current `P4CHARSET` and the server disagree, stop and report the verified mismatch instead of guessing a silent workaround.
- Do not guess stream names.
- You may derive a new local workspace name or local root from confirmed team rules, existing client naming patterns, `P4CLIENT`, host defaults, or a user-confirmed base path.
- Do not present a derived local workspace name or root as if it were a verified server-side fact.
- For large workspaces, stop after creation and ask whether the user wants to continue in P4V. Do not start command-line `sync` unless they explicitly asked for it.