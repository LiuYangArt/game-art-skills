---
name: perforce-p4
description: Use when working against Perforce Helix Core through the p4 CLI, including first-time local setup or "p4-init" onboarding, workspace inspection, changelists, stream or branch merges, resolves, and conflict-heavy depot operations that should use a local JSON connection profile or a team onboarding document.
---

# Perforce P4

## Overview

This skill now supports two modes:

- `p4-init` / onboarding: set up a Windows machine, log in, create stream workspaces, and prepare a local connection profile
- day-2 operations: run `p4` safely through the checked-in wrapper script after setup is complete

The init flow is documented in [references/init-and-onboarding.md](references/init-and-onboarding.md).
The normal command wrapper is [scripts/Invoke-P4.ps1](scripts/Invoke-P4.ps1).

## Shared Defaults

Use [config/p4-init.defaults.json](config/p4-init.defaults.json) for safe team-shared defaults such as:

- server address
- charset
- install package id
- recommended local root base paths
- workspace naming patterns
- role to stream recommendations

Keep secrets out of that file.

Use [config/p4-connection.json](config/p4-connection.json) only for the local machine. It is ignored by git.

## Init And Onboarding

When the user says `p4-init`, "初始化 p4", "新人安装 p4", or asks to set up a local workspace from scratch:

1. If the user supplied an onboarding doc path or link, read it first.
2. Then read [references/init-and-onboarding.md](references/init-and-onboarding.md).
3. Extract fixed information from the doc or defaults file.
4. Ask only for missing or sensitive values:
   - username
   - password
   - project stream
   - engine stream when needed
   - local roots
   - workspace names
5. Prefer `p4 login` ticket flow. Do not persist the password unless the user explicitly asks.
6. Run [scripts/p4-init.ps1](scripts/p4-init.ps1) to execute install, login, workspace creation, optional sync, and optional local config generation.
7. If engine branch or stream is not known, stop and ask. Do not guess.

Example:

```powershell
pwsh -File .\skills\perforce-p4\scripts\p4-init.ps1 -User liuyang -ProjectStream //streammain/dev -Sync -WriteConnectionConfig
```

Use `-WhatIf` for a dry run preview.

## Day-2 Command Entry Point

Use the wrapper instead of raw `p4` when possible:

```powershell
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 info
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 client -o
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 opened
```

`Invoke-P4.ps1` works with either:

- a local password stored in `config/p4-connection.json`
- or an existing `p4 login` ticket when `password` is blank

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
- If the server uses `ssl:`, handle trust explicitly before retrying the command.
- During onboarding, do not guess engine stream, workspace naming rules, or local root paths when the team doc is incomplete.