---
name: unreal-ecabridge-pcg
description: Use when creating, inspecting, repairing, or validating Unreal PCG graphs in the Paralogue project through ECABridge MCP, including reusable scatter graph topology, graph parameter wiring, symmetric offset/rotation ranges, PCGVolume overlap exclusion, mesh spawners, defaults, and source-control checks.
---

# Unreal ECABridge PCG

Use this skill for reusable PCG graph work in `F:\P4V\liuyang_HOMEPCWS_Env` through ECABridge. Do not assume a fixed graph asset path; always inspect or ask for the target graph path.

## Core Rule

This skill is for building and repairing new PCG graphs too. Treat any concrete graph path, node id, or asset path as an example unless the user explicitly names it.

## Script Use

Use the bundled scripts for repeatable checks, but always pass `--graph` explicitly:

```powershell
python .agents\skills\unreal-ecabridge-pcg\scripts\pcg_scatter_tools.py validate --graph "/Game/Path/PCG_MyScatter"
python .agents\skills\unreal-ecabridge-pcg\scripts\pcg_scatter_tools.py repair-scatter --graph "/Game/Path/PCG_MyScatter"
```

Commands:

- `validate`: check parameters, getter nodes, required edges, and `validate_asset`.
- `wire-params`: create/reuse graph parameter getter nodes and connect pins.
- `set-defaults`: patch existing `UserParameters` defaults through `InstancedPropertyBag` text.
- `repair-scatter`: apply the standard scatter wiring/default pattern, save, validate.
- `scripts/eca_call.py`: low-level JSON-RPC wrapper for one ECABridge tool call.

Use `--mapping-json @path.json` for custom node ids or pin maps. Use `--values-json @path.json` to override defaults.

## Default Workflow

1. Inspect first:
   - `dump_pcg_graph` for nodes, pins, edges, parameters.
   - `list_pcg_node_types` / `get_pcg_node_pins` when class or pin names are uncertain.
   - `execute_script` only when ECABridge dumps do not expose needed settings/defaults.
2. Source control:
   - Existing asset: `check_out_asset` before edits.
   - New graph: create/save, then `mark_for_add` or verify P4 state.
   - Never submit unless explicitly requested.
3. Edit with PCG tools or scripts:
   - `create_pcg_graph`, `add_pcg_node`, `set_pcg_node_property`, `connect_pcg_nodes`.
   - Batch fragile Python-only work through `execute_script`.
4. Save:
   - `unreal.EditorAssetLibrary.save_asset(graph_path, only_if_is_dirty=False)`.
5. Validate before final reply:
   - `validate_asset` plus `dump_pcg_graph` edge/parameter checks.
   - `get_source_control_status` or relevant P4 command.

## Parameter Schema Limit

ECABridge/Python can reliably edit getter nodes, node properties, edges, and existing default values. It cannot safely rename/add/remove graph parameter schema fields inside the `UserParameters` property bag. If parameter names or types must change, have the user do that in the Editor UI, then reconnect getters and validate.

## Reusable Scatter Parameters

Preferred generic scatter parameters:

- `Meshes`: StaticMesh array, at least one default mesh for smoke testing.
- `VoxelSize`: FVector density/spacing.
- `OffsetRange`: FVector symmetric random offset range.
- `RotationRange`: FVector/Rotator symmetric random rotation range.
- `ScaleMin`: FVector minimum random scale.
- `ScaleMax`: FVector maximum random scale.
- `UniformScale`: bool, use X scale range when true.

Safe cube-test defaults:

- `VoxelSize = (180,180,180)`
- `OffsetRange = (0,0,0)`
- `RotationRange = (0,0,0)`
- `ScaleMin = (1,1,1)`
- `ScaleMax = (1,1,1)`
- `UniformScale = true`

Do not leave `VoxelSize`, `ScaleMin`, or `ScaleMax` at `(0,0,0)`.

## Getter Wiring Pattern

For each graph parameter use a `PCGGenericUserParameterGetSettings` node:

- `PropertyPath = <ParamName>`
- `OutputAttributeName = <ParamName>`
- getter `Out` connects to the target override pin.

Common scatter wiring:

- `Meshes` -> mesh selector data, commonly `MatchAndSetAttributes.Match Data`.
- `VoxelSize` -> `VolumeSampler.VoxelSize`.
- `OffsetRange` -> `TransformPoints.OffsetMax`.
- `OffsetRange` -> metadata math `NEGATE` -> `TransformPoints.OffsetMin`.
- `RotationRange` -> `TransformPoints.RotationMax`.
- `RotationRange` -> metadata math `NEGATE` -> `TransformPoints.RotationMin`.
- `ScaleMin` -> `TransformPoints.ScaleMin`.
- `ScaleMax` -> `TransformPoints.ScaleMax`.
- `UniformScale` -> `TransformPoints.bUniformScale`.

In this UE build, `PCGMetadataMathsSettings` input pins are named `InputSource1`, `InputSource2`, `InputSource3`; do not assume `InA`/`InB`.

## Multi-Mesh Scatter Pattern

1. Create `Meshes` as a StaticMesh array graph parameter.
2. Add a getter for `Meshes`.
3. Feed it to the mesh selection path, for example `MatchAndSetAttributes.Match Data`.
4. Configure the spawner to use `PCGMeshSelectorByAttribute` with `AttributeName = Meshes`.
5. Keep a valid default mesh for validation.

## PCGVolume Overlap Exclusion

Use this topology when overlapping PCGVolumes should not double-spawn:

1. Get self volume: `PCGGetVolumeSettings` selecting self PCGVolume.
2. Get overlapping peer volumes: `PCGGetVolumeSettings` selecting PCGVolume actors, must overlap self, ignore self.
3. Feed self into `PCGDifferenceSettings.Source`.
4. Feed peers into `PCGDifferenceSettings.Differences`.
5. Feed difference output into `PCGVolumeSamplerSettings.Volume`.
6. Continue with pruning, transform randomization, and spawning.

## Debugging Rules

- Do not guess property, class, or pin names when tools can inspect them.
- If ECABridge returns an error, surface the exact failing command and reason.
- When changing defaults through `InstancedPropertyBag.import_text`, first read `export_text`, preserve the schema/path, change only intended values, save, and re-read.
- If a target override pin accepts one connection and is already connected, reuse or deliberately rewire; do not stack accidental duplicate edges.
- Runtime validation needs an actor name; use `run_pcg_on_actor`, then `dump_pcg_data` when the user provides one.