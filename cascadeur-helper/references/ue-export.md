# Cascadeur to Unreal export notes

Use this file when the question is not just about animation inside Cascadeur, but about getting the result into Unreal Engine.

## Main idea

A good export is mostly about consistency:
- same skeleton expectation,
- sane root orientation,
- baked keys,
- predictable FBX import settings.

## Before export

Check these first:

1. The character uses the skeleton you actually want in Unreal.
2. The weapon is either:
   - only a scene prop for animation authoring, or
   - something you intentionally want exported too.
3. The final animation is baked cleanly enough that Unreal will not depend on editor-only helpers.

## Common risk areas

### Skeleton mismatch

If the target skeletal mesh in Unreal uses a different hierarchy or naming convention, the animation may import badly or need retargeting.

### Root and orientation

If the character faces the wrong way or root motion behaves strangely, inspect:
- forward axis,
- up axis,
- root bone orientation,
- whether root motion should be exported at all.

### Constraints not reflected in final keys

If the motion looks right in Cascadeur but wrong in Unreal, suspect that helper relationships were not baked into the exported animation result.

### Weapon expectations

Often in Unreal the weapon is attached in-engine by socket, not embedded into the character animation asset.
So distinguish between:
- animating with a gun as a visual guide,
- exporting the character body animation,
- attaching the real gameplay weapon later in UE.

## Recommended answer pattern

When the user asks an export question, answer in this order:
1. what they are trying to export,
2. what Unreal expects,
3. what to check before export,
4. what import symptoms usually mean.

## Useful practical advice

- Prefer stable body animation first; let Unreal sockets handle the runtime weapon when possible.
- If hands line up in Cascadeur but not in Unreal, check weapon socket placement before redoing the animation.
- If root motion is involved, call it out explicitly and keep it intentional.
