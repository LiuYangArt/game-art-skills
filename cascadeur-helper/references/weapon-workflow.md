# Weapon workflow

This is the default beginner workflow for making a character hold a gun in Cascadeur.

## Goal

Get a stable, easy-to-edit weapon setup before polishing the animation.

## Preferred order

1. Import the character.
2. Import the gun as a prop.
3. Attach the gun to the main hand.
4. Pose the main hand around the grip.
5. Move the support hand into place.
6. Only add constraints if the support hand will not stay aligned.
7. Polish torso, shoulders, head, and recoil after the hold is stable.

## Main-hand-first rule

For rifles and pistols, choose one hand as the driver.
Usually this is the right hand for a right-handed character.

Why:
- it keeps the setup simpler,
- it avoids fighting constraints on both hands at once,
- it makes later pose changes easier.

## Attachment options

### Option A: simple prop mesh attached to hand

Use this first.

When to use:
- the gun is just a mesh,
- you mainly need the character to animate while holding it,
- you want the simplest setup.

Practical idea:
- attach the gun mesh to the hand joint,
- or to `weapon_r` if the character rig provides that joint.

### Option B: gun has its own joints

Use this when:
- the gun was imported with a small rig,
- you need a cleaner hierarchy,
- you may animate parts of the gun later.

Practical idea:
- attach the gun root joint under the character hand-related joint,
- then orient the gun correctly before posing the fingers.

## Support hand stabilization

If the left hand keeps drifting:

1. first check whether the gun transform is already final,
2. then place the left hand near the correct contact point,
3. only then add a constraint.

Use constraints as a stabilizer, not as the first pose-building tool.

### Typical use cases

- hand to rifle foregrip
- hand to barrel guard area
- off-hand should keep following the weapon during aim or recoil

## Beginner-safe advice

- Do not start with both hands constrained.
- Do not chase finger detail before the gun position is correct.
- Do not solve recoil first; solve the hold first.
- If the pose looks wrong, fix clavicle / shoulder / elbow flow before blaming the hand.

## If the user asks for specific setups

### Pistol, one hand

Recommend:
- attach the pistol to the dominant hand,
- build a clean wrist and elbow line,
- add the second hand only if the animation needs a two-hand grip.

### Rifle, two hands

Recommend:
- attach rifle to dominant hand or weapon joint,
- align the stock and grip,
- place support hand on the foregrip,
- use a light constraint only if needed.

### Aiming pose

Recommend order:
1. weapon alignment,
2. main hand,
3. support hand,
4. shoulders,
5. chest rotation,
6. head / eyes.
