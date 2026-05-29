# Cascadeur doc map

Use this file to route quickly before opening more detailed references.

## Official entry

- Main help: <https://cascadeur.com/help>

## High-value sections for common questions

### Import / scene setup
Keywords:
- import fbx
- add model
- scene
- rig
- character setup

Typical use:
- user cannot get a character or weapon into the scene
- user asks whether to import as new scene or add to existing scene

### Props / objects / weapon attachment
Keywords:
- props
- adding objects
- weapon
- parent to joint
- weapon_r

Typical use:
- character should hold a gun, sword, or tool
- user asks how to attach an object to a hand

### Constraints
Keywords:
- constraints
- constrain points
- constrain transform
- point controller

Typical use:
- support hand slides off the rifle
- object should follow a hand or another object

### Rigging props
Keywords:
- rigging props
- prop joint
- root joint

Typical use:
- gun has its own joint hierarchy
- user wants a cleaner prop setup than a plain mesh parent

### Posing / animation tools
Keywords:
- posing
- auto posing
- interpolation
- trajectory

Typical use:
- user already attached the weapon but the pose looks bad
- user wants cleaner recoil, aiming, or idle shapes

### Physics / AutoPhysics / overlap cleanup
Keywords:
- autophysics
- secondary motion
- overlap
- collisions

Typical use:
- user wants body follow-through after key poses are blocked
- animation feels stiff and needs natural settling

### Export
Keywords:
- export fbx
- bake animation
- unreal
- skeleton

Typical use:
- user wants to send the animation to UE5.x
- user has mismatched orientation, missing keys, or odd root motion after export

## Fast routing recipes

### “How do I make the character hold a gun?”
Open:
1. props / adding props
2. rigging props if the gun has joints
3. constraints if the second hand needs stabilization

### “My left hand keeps drifting off the rifle.”
Open:
1. constraints
2. point or transform constraint pages
3. posing pages only after the base pose is corrected

### “How do I get this into Unreal?”
Open:
1. export docs
2. then read `ue-export.md`
