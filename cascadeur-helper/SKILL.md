---
name: cascadeur-helper
description: Use when the task is about Cascadeur animation workflows, official help pages, beginner guidance, prop or weapon handling, constraints, or exporting character animation to Unreal Engine. Prefer this skill when the user is new to Cascadeur and wants step-by-step, doc-backed instructions.
---

# Cascadeur Helper

## Overview

Use this skill when answering Cascadeur questions, especially for beginners. Focus on doc-backed, executable steps rather than broad theory.

Default outcome:
1. identify the animation task,
2. locate the most relevant official help section,
3. explain the steps in beginner-safe language,
4. connect the answer to Unreal Engine export or game-animation use when relevant.

## Default workflow

1. Classify the request into one of these buckets:
   - import or scene setup
   - prop or weapon attachment
   - constraints or hand fixing
   - posing or motion polishing
   - physics / AutoPhysics / secondary motion
   - export to Unreal Engine
2. Read `references/doc-map.md` first to find the likely official section.
3. If the task is about holding a weapon or attaching an object, also read `references/weapon-workflow.md`.
4. If the task is about Unreal handoff, also read `references/ue-export.md`.
5. If the user sounds blocked or confused, also read `references/newbie-troubleshooting.md` and answer in smaller steps.

## Response style

- Assume the user is new unless they say otherwise.
- Prefer concrete UI actions over abstract terminology.
- Explain Cascadeur terms briefly the first time they appear.
- When the docs are ambiguous, say what is confirmed by docs vs what is practical advice.
- For weapon animation, prefer the simplest stable setup first: attach the weapon to the main hand, then solve the support hand.

## Common task routing

### Importing a character or prop

Start with `references/doc-map.md`.
Look for import, scene, rig, and object setup pages.

### Making a character hold a gun

Read `references/weapon-workflow.md`.
Typical order:
1. import character and gun,
2. attach the gun to the main hand or `weapon_r` if present,
3. pose the main hand,
4. place the support hand,
5. add constraints only if the support hand drifts.

### Fixing a slipping left hand on a rifle

Read `references/weapon-workflow.md` and the constraints section in `references/doc-map.md`.
Prefer point or transform constraints only after the base pose is already close.

### Exporting animation to Unreal Engine

Read `references/ue-export.md`.
Focus on skeleton consistency, root orientation, naming, baking, and FBX export checks.

## Guardrails

- Do not invent exact menu names when not confirmed.
- Do not overcomplicate beginner answers with full rig theory.
- Do not recommend a dual-hand constraint setup as the first step unless the simple parented-weapon setup already fails.
- Do not assume Cascadeur and Unreal retarget settings will magically match; call out skeleton and axis checks.

## References

- `references/doc-map.md` — quick map of official help areas and keywords
- `references/weapon-workflow.md` — hand-held weapon workflow for beginners
- `references/ue-export.md` — Cascadeur to Unreal export notes
- `references/newbie-troubleshooting.md` — common beginner failure modes and recovery steps
