# Newbie troubleshooting

Use this when the user sounds blocked, confused, or frustrated.

## Default teaching style

- Explain one decision at a time.
- Give a short goal before listing clicks.
- Avoid dropping many new terms in one answer.
- When possible, separate “must do now” from “optional later”.

## Common failure modes

### “I imported it but nothing makes sense.”

Response pattern:
1. confirm what objects are in scene,
2. identify the character object,
3. identify the gun object,
4. explain the next single step only.

### “I attached the gun but the pose looks awful.”

Likely issue:
- attachment is fine,
- upper-body pose is not.

Tell the user to check:
- wrist angle,
- elbow placement,
- shoulder height,
- chest rotation.

### “The second hand won’t stay on the weapon.”

Likely issue:
- trying to solve support-hand stability too early.

Tell the user to:
1. lock the weapon position first,
2. pose the main hand first,
3. place the support hand,
4. then try a constraint if needed.

### “It worked in Cascadeur but breaks in Unreal.”

Likely issue buckets:
- export bake problem,
- root / axis mismatch,
- Unreal socket mismatch,
- skeleton mismatch.

## Preferred answer structure

1. short diagnosis,
2. exact next step,
3. what result they should expect,
4. what to do if that result does not happen.

## Example tone

Good:
- “先别管左手。先把枪固定到右手，并把右手握把姿势做对。”
- “如果枪的位置已经对了，左手再用约束补稳定，不要一开始双手一起锁。”

Avoid:
- long theory dumps,
- full rigging lectures for a simple hold-gun question,
- assuming the user already understands controllers, points, and transforms.
