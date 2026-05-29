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
For stream up-copy work, confirm both sides before touching files:

```powershell
p4 info
p4 stream -o
p4 clients -u $env:USERNAME
p4 interchanges -S //parent/stream -P //child/stream
p4 interchanges -S //child/stream -P //parent/stream
```

`p4 stream -o` identifies the active stream and parent. `p4 clients -u` helps locate an existing target-stream workspace when the current client cannot write the target stream.

## 2. Preview Before Any Merge

Choose the narrowest preview that matches the existing repo pattern:

- Explicit path mapping: `integrate -n //source/... //target/...`
- Existing branch spec: `integrate -n -b branchName`
- Stream workflow already in use: `merge -n ...` against the established stream/client pattern

Review the preview output and confirm the file set looks correct before repeating the command without `-n`.

## 3. Stream Down-Merge Before Up-Copy

When copying a child stream up to its parent, clear parent-to-child merge debt first. Perforce may reject a child-to-parent copy with `Stream ... cannot 'copy' over outstanding 'merge' changes` even when the requested copy path is narrow. Check outstanding parent changes against the whole stream, not only the requested subpath.

Recommended sequence:

1. In the child stream workspace, run the parent-to-child merge first, using the narrow requested path when possible.
2. If up-copy is still blocked, run `p4 interchanges -S //parent -P //child` and merge only the remaining blocking files needed to clear stream debt.
3. Resolve safely with `p4 resolve -as`; if files remain in `p4 resolve -n`, stop and report that unresolved list for user judgment.
4. Submit the down-merge before switching to the parent stream workspace for the up-copy.
5. In the parent stream workspace, run `p4 copy --from Child path/...`, then verify `p4 resolve -n`, `p4 opened`, and submit only when requested.

For stream-relative commands, prefer server suggestions such as `p4 merge --from Art Content/...` or `p4 copy --from Env Content/...` over hand-built depot-to-depot paths when the server says a stream view is required.
Use `scripts/Invoke-P4StreamUpCopy.py` for this workflow when possible. It defaults to dry-run and requires `--execute` to open files and `--submit` to submit.

```powershell
python scripts/Invoke-P4StreamUpCopy.py --parent //streammain/Art --child //streammain/Env --path Content/... --parent-client my_art_client --parent-cwd F:\P4V\my_art_workspace --child-cwd F:\P4V\my_env_workspace
```

Add `--clear-stream-debt` only when the user agrees to merge remaining parent-to-child debt outside the requested path. Add `--backup-clobber` only when backing up unversioned local files is acceptable.

## 4. Resolve In Layers

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

## 5. Inspect Conflicts Deliberately

For files that need manual judgment, gather enough context to explain the change:

```powershell
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 diff
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 diff2 //source/file //target/file
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 filelog -m 5 //depot/path/file
```

Combine depot history with the local file contents. When the workspace file needs manual edits, edit the file directly, then continue the resolve flow with the narrowest command that marks only the intended file set as resolved.

## 6. Validate Before Submit

At minimum:

```powershell
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 opened
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 diff -se
pwsh -File .\skills\perforce-p4\scripts\Invoke-P4.ps1 diff -du
```

Then run the smallest relevant project validation: build, targeted tests, asset checks, or any repo-specific verification that covers the merged area.

Only submit if the user asked for it. If submit is requested, describe the resolved scope and validation first.

## 7. Recovery Patterns

- Wrong workspace or wrong target: stop, inspect `client -o`, and fix the context before continuing.
- Unexpected file explosion in preview: abort and narrow the branch spec, stream, or depot path.
- Too many unresolved files for manual review: split the work by path or changelist instead of forcing one huge resolve.
- P4V default changelist is only the default open-files bucket. If the merge should land as one batch, move or reopen all relevant files into the target changelist before resolve or submit; do not treat default as a separate branch or merge state.
- Labels like no-upload are descriptions only; decide by opened or resolved state, not by the label text.
- Use [scripts/Reopen-P4Changelist.py](../scripts/Reopen-P4Changelist.py) to move scoped files into one changelist before resolve or submit.
- Use [scripts/Check-P4MergeReady.py](../scripts/Check-P4MergeReady.py) as the final guard before submit.
- Password or auth failures: verify config/p4-connection.json, then test with info before retrying write operations.
- `Must use a stream view`: switch to stream-relative syntax, for example `p4 merge --from Parent path/...` or `p4 copy --from Child path/...` from the correct stream workspace.
- `cannot 'copy' over outstanding 'merge' changes`: finish parent-to-child stream merge debt first, then submit that down-merge before retrying child-to-parent copy.
- Target stream not in client view: use an existing target-stream workspace, or create/switch to one; a child workspace cannot submit files in the parent stream.
- SSL trust prompt on a known alternate server name: do not blindly trust; compare with an already trusted `P4PORT` or ask the user to confirm the fingerprint.
- `Can't clobber writable file`: inspect whether the local file is unversioned. If it may contain user data, compare size/hash and move it to an explicit backup path before retrying the sync/copy.
- Long-running `p4 copy` or `p4 resolve` timeouts may still leave opened files. After any timeout, check `p4 opened` and `p4 resolve -n` before retrying.
