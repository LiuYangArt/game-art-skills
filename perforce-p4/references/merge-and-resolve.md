# Merge And Resolve

Use this workflow for tricky Perforce operations: integrating branches, merging streams, resolving conflicts, or cleaning up a half-finished changelist.

## 1. Establish Context

Run the wrapper first and confirm the workspace and server match the intended target:

```powershell
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 info
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 client -o
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 opened
```

Then inspect the topology already present in the depot:

```powershell
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 streams
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 branches
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 interchanges //source/... //target/...
```

Use explicit depot paths, branch specs, or stream specs that already exist in the repo. Do not guess.

## 2. Preview Before Any Merge

Choose the narrowest preview that matches the existing repo pattern:

- Explicit path mapping: `integrate -n //source/... //target/...`
- Existing branch spec: `integrate -n -b branchName`
- Stream workflow already in use: `merge -n ...` against the established stream/client pattern

Review the preview output and confirm the file set looks correct before repeating the command without `-n`.

## 3. Resolve In Layers

After the integrate or merge runs:

```powershell
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 resolve -n
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 opened
```

Recommended order:

1. Use safe automatic resolve only where it is obviously appropriate for the whole subset.
2. Inspect the remaining files one by one.
3. Read the workspace file plus the relevant depot context before deciding how to finish the resolve.
4. Re-run `resolve -n` until no unresolved files remain.

Avoid blanket accept flags over the whole changelist unless the user explicitly wants that policy and the file set justifies it.

## 4. Inspect Conflicts Deliberately

For files that need manual judgment, gather enough context to explain the change:

```powershell
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 diff
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 diff2 //source/file //target/file
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 filelog -m 5 //depot/path/file
```

Combine depot history with the local file contents. When the workspace file needs manual edits, edit the file directly, then continue the resolve flow with the narrowest command that marks only the intended file set as resolved.

## 5. Validate Before Submit

At minimum:

```powershell
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 opened
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 diff -se
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 diff -du
```

Then run the smallest relevant project validation: build, targeted tests, asset checks, or any repo-specific verification that covers the merged area.

Only submit if the user asked for it. If submit is requested, describe the resolved scope and validation first.

## 6. Recovery Patterns

- Wrong workspace or wrong target: stop, inspect `client -o`, and fix the context before continuing.
- Unexpected file explosion in preview: abort and narrow the branch spec, stream, or depot path.
- Too many unresolved files for manual review: split the work by path or changelist instead of forcing one huge resolve.
- Password or auth failures: verify `config/p4-connection.json`, then test with `info` before retrying write operations.