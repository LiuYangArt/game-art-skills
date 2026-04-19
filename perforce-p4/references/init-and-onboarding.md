# Init And Onboarding

Use this reference when the user wants first-time local setup, says `p4-init`, asks to install Perforce on a new Windows machine, or gives you a team onboarding document and wants you to follow it.

## Summary Of The Agreed Workflow

From the earlier design discussion, the stable workflow is:

1. Read team defaults and any onboarding doc first.
2. Ask only for missing or sensitive fields.
3. Prefer `p4 login` ticket flow over storing passwords in JSON.
4. Create project workspace first.
5. Only create engine workspace when the engine stream is explicitly known.
6. Only sync after the user confirmed the target stream and local path.

## Inputs

### Team-shared inputs

Read these first when available:

- [config/p4-init.defaults.json](../config/p4-init.defaults.json)
- a team onboarding markdown file, local path, or accessible URL supplied by the user

Expected non-sensitive information from team inputs:

- server address from a private onboarding doc or other private team material
- install method
- recommended project root base path
- recommended engine root base path
- workspace naming rule
- role to stream mapping
- whether engine should live in a separate workspace

### User-supplied inputs

Only ask the user for what the team inputs do not already answer, especially:

- server, when the onboarding doc or private defaults do not provide it
- username
- password
- project stream
- engine stream, when needed
- final local root paths
- final workspace names if they want overrides

## Recommended Agent Flow

1. If the user provided an onboarding doc path or link, read it first.
2. Load [config/p4-init.defaults.json](../config/p4-init.defaults.json).
3. Reconcile the two sources. If they conflict, ask the user which one wins.
4. Ask only for missing or sensitive values.
5. If engine stream is still unknown, stop and ask. Do not guess.
6. Run [scripts/p4-init.ps1](../scripts/p4-init.ps1).
7. Summarize the final server, stream, local root, and workspace names back to the user.

## Script Usage Pattern

Typical project-only setup:

```powershell
pwsh -File .\skills\perforce-p4\scripts\p4-init.ps1 -InstallIfMissing -Server perforce.example:1666 -User alice -Password '<secret>' -ProjectStream //streammain/dev -Sync -WriteConnectionConfig
```

Project plus engine:

```powershell
pwsh -File .\skills\perforce-p4\scripts\p4-init.ps1 -InstallIfMissing -Server perforce.example:1666 -User alice -Password '<secret>' -ProjectStream //LovecraftMain/Env -EngineStream //SomeDepot/EngineBranch -ProjectRoot D:\Perforce\Project\Env -EngineRoot D:\Perforce\Engine\EngineBranch -Sync -WriteConnectionConfig
```

Preview only:

```powershell
pwsh -File .\skills\perforce-p4\scripts\p4-init.ps1 -Server perforce.example:1666 -User alice -ProjectStream //streammain/dev -WhatIf
```

## Non-Negotiable Rules

- Do not guess engine branch or stream.
- Do not store the password unless the user explicitly asked for persistent local storage.
- Do not overwrite an existing non-empty workspace root unless the user explicitly confirmed and you use `-Force`.
- Do not create or sync workspaces into a path the user has not confirmed.
- For very large projects, treat `-Sync` as a confirmation point, not an automatic default.