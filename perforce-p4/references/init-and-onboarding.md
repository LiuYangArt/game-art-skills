# Init And Onboarding

Use this reference when the user wants first-time local setup, says `p4-init`, asks to install Perforce on a new Windows machine, or gives you an onboarding document and wants you to follow it.

## What `p4-init` Is For

`p4-init` is the machine-bootstrap flow for Perforce. Its job is to:

- install `p4` or `P4V` when needed
- verify SSL trust
- verify the live server charset mode
- log in or reuse an existing ticket
- inspect streams when needed
- create stream workspaces
- optionally write the local connection profile

It is not responsible for carrying project-specific stream maps or role-to-stream rules inside the skill itself.
If a project needs those, they should come from a user-supplied onboarding document or the current conversation.

## Shared Defaults vs Local Config

Use [config/p4-init.defaults.json](../config/p4-init.defaults.json) only for generic shared defaults:

- install method
- recommended local root base paths
- workspace naming rule

Use [config/p4-connection.json](../config/p4-connection.json) for local machine connection data only:

- server
- user
- optional saved password

Do not put project-specific depot names, stream maps, or real team onboarding content into shared defaults.

## Summary Of The Agreed Workflow

1. Read any onboarding doc first.
2. Load the generic defaults file.
3. Read the local connection profile when present.
4. Resolve `server`, `user`, and optional `password` from prompt first, then onboarding doc, then local connection config.
5. For `ssl:` servers, verify trust state before login or workspace creation.
6. Verify the live server charset state with real `p4` commands before assuming Unicode vs non-Unicode.
7. Separate server facts from local creation choices.
8. Ask only for missing or sensitive fields.
9. Create the requested workspace.
10. After creating the workspace, prefer handing off to P4V for the actual sync unless the user explicitly asked for command-line `sync`.

## Live Charset Verification

Before using team memory or old onboarding notes to decide charset behavior, run real checks against the target server.

Recommended sequence:

```powershell
p4 -p <server> -u <user> info
p4 -p <server> -u <user> counter unicode
```

Interpretation:

- If `counter unicode` returns `1`, the server is Unicode-enabled. Keep using a Unicode-capable client environment and verify the current `P4CHARSET` actually works.
- If `counter unicode` returns `0`, the server is non-Unicode. Use `-C none` or an equivalent non-Unicode client environment.
- If the current environment fails, compare it with an explicit `-C none` probe before deciding what is wrong:

```powershell
p4 -p <server> -u <user> -C none counter unicode
```

- If the default call fails but `-C none` returns `0`, the server is non-Unicode and the current `P4CHARSET` is incompatible.
- If the default call fails but `-C none` returns `1` or says unicode-only, the server is Unicode-enabled and the current client charset setup is wrong.

Do not present old notes or previous sessions as current truth unless the live checks still match.

## Stream Discovery

If the user does not know the target stream yet:

1. Check the onboarding document first.
2. If still unknown, list streams against the real server.
3. Ask the user to confirm the exact stream to use.

Example:

```powershell
p4 -p <server> -u <user> streams
```

Do not infer stream names from role names or prior projects.

## Local Creation Choices

When creating a new workspace, treat these as local choices rather than server facts:

- client or workspace name
- local root path
- whether you follow a team naming pattern for the new client

These local choices may be derived from:

- a user-confirmed base path
- an onboarding document that defines the naming rule
- existing visible client naming patterns from live commands such as `p4 clients -u <user>` or `p4 client -o <name>`
- `P4CLIENT`
- the local host name, when Perforce falls back to it for a new client

When you derive one of these values, say so explicitly. Example: "I am creating local workspace `alice_HOMEPCWS_Engine` under `F:\P4V` based on the existing client naming pattern."

## Inputs

### Team-shared inputs

Read these first when available:

- [config/p4-init.defaults.json](../config/p4-init.defaults.json)
- a team onboarding markdown file, local path, or accessible URL supplied by the user

Expected non-sensitive information from team inputs:

- install method
- recommended local root base path
- workspace naming rule
- project-specific stream information when the user explicitly supplied an onboarding doc

### Local machine inputs

Use [config/p4-connection.json](../config/p4-connection.json) when present for:

- server
- user
- optional saved password

### User-supplied inputs

Only ask the user for what the onboarding doc and local connection config do not already answer, especially:

- server
- username
- password
- project stream
- engine stream, when needed
- final local root paths, when no confirmed base path or naming rule already gives one
- final workspace names, when no override or visible naming pattern already gives one

## Recommended Agent Flow

1. If the user provided an onboarding doc path or link, read it first.
2. Load [config/p4-init.defaults.json](../config/p4-init.defaults.json).
3. Read [config/p4-connection.json](../config/p4-connection.json) if it exists.
4. Resolve connection inputs in this order: prompt, onboarding doc, local connection config.
5. Verify trust, then verify live charset state with real `p4` commands.
6. If the stream is unknown, list streams before asking the user to choose.
7. If creating a new workspace without an explicit local name or root, derive the local values from visible rules or patterns and state that choice explicitly.
8. Run [scripts/p4-init.ps1](../scripts/p4-init.ps1) without `-Sync` by default.
9. Summarize the final server, verified charset mode, stream, local root, and workspace names back to the user.
10. Ask whether the user wants to continue syncing in P4V. Only use `-Sync` if they explicitly want command-line sync.

## Script Usage Pattern

Typical project-only setup:

```powershell
pwsh -File .\skills\perforce-p4\scripts\p4-init.ps1 -InstallIfMissing -Server perforce.example:1666 -User alice -Password '<secret>' -ProjectStream //streams/dev -WriteConnectionConfig
```

Project plus engine:

```powershell
pwsh -File .\skills\perforce-p4\scripts\p4-init.ps1 -InstallIfMissing -Server perforce.example:1666 -User alice -Password '<secret>' -ProjectStream //streams/project-main -EngineStream //streams/engine-main -ProjectRoot D:\Perforce\Project\project-main -EngineRoot D:\Perforce\Engine\engine-main -WriteConnectionConfig
```

Only when the user explicitly wants command-line sync:

```powershell
pwsh -File .\skills\perforce-p4\scripts\p4-init.ps1 -InstallIfMissing -Server perforce.example:1666 -User alice -Password '<secret>' -ProjectStream //streams/dev -Sync
```

Preview only:

```powershell
pwsh -File .\skills\perforce-p4\scripts\p4-init.ps1 -Server perforce.example:1666 -User alice -ProjectStream //streams/dev -WhatIf
```

## Non-Negotiable Rules

- Do not guess stream names.
- Do not guess the server charset mode from prior notes; verify it live each time the server or environment may have changed.
- Do not present a derived local workspace name or local root as if it were a verified server-side fact.
- Do not store the password unless the user explicitly asked for persistent local storage.
- Do not overwrite an existing non-empty workspace root unless the user explicitly confirmed and you use `-Force`.
- Do not create or sync workspaces into a path the user has not confirmed.
- For very large projects, treat `-Sync` as an explicit opt-in, not an automatic default.
- When the workspace is ready, prefer telling the user to continue in P4V so they can see sync progress.