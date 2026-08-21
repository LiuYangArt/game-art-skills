---
name: unreal-pcg-hlsl-node
description: Generate paste-ready Unreal Engine 5.7 PCG Custom HLSL nodes with configured pins, correctly separated Shader Functions and Shader Source, specifications, and lightweight validation. Use for PCG GPU Point Generator, Point Processor, Attribute Set Processor, or Custom kernels.
---

# Unreal PCG HLSL Node

## Overview

Turn PCG generation logic into a `PCG Custom HLSL` node that users can copy from a file and paste directly into a PCG graph. The generated node must already contain its data pins, `Shader Functions`, `Shader Source`, kernel type, element count, and seed.

## Workflow

1. Classify the kernel before writing code:
   - `PointProcessor`: one output point per input point; use for modifying position, rotation, scale, density, seed, or custom attributes.
   - `PointGenerator`: create points from `NumElements`; use for grids, random scatters, rings, volumes, and fixed procedural point sources.
   - `AttributeProcessor`: process Attribute Set rows, not point data.
   - `Custom`: use only when pin layout, thread count, or output cardinality cannot fit the preset kernels.
2. Write the node specification first: kernel type, typed data pins, output initialization source, element count, seed, output attributes, and downstream consumers.
3. Split authored HLSL by editor field before delivery:
   - `Shader Functions`: helper constants and helper functions only.
   - `Shader Source`: the per-thread executable body. For preset kernels, engine-generated declarations already provide values such as `ThreadIndex`, `In_DataIndex`, `Out_DataIndex`, and `ElementIndex`; do not wrap this body in `Main()`.
4. Generate artifacts with `scripts/emit_pcg_hlsl_artifacts.py`; do not hand-write export text. Its paste artifact preserves both `ShaderFunctions` and `ShaderSource` and creates the requested PCG data pins.
5. Run `scripts/validate_pcg_hlsl.py` for static checks. Treat it as a syntax/sanity pass only; final truth is Unreal compile/runtime logs.
6. If applying to a real graph, use ECA Bridge or Editor UI to place/configure the node, then run PCG and inspect `Saved/Logs/Paralogue.log`.

## Script Usage

Generate a Landscape-driven Point Generator artifact set:

```powershell
python .agents\skills\unreal-pcg-hlsl-node\scripts\emit_pcg_hlsl_artifacts.py `
  --name building-scatter `
  --kernel-type PointGenerator `
  --functions-file C:\Temp\building_functions.hlsl `
  --source-file C:\Temp\building_source.hlsl `
  --input-pin Landscape:landscape `
  --output-pin Out:point `
  --num-elements 1024 `
  --out-dir C:\Users\LiuYang\Desktop
```

Generate a Custom kernel with extra pins:

```powershell
python .agents\skills\unreal-pcg-hlsl-node\scripts\emit_pcg_hlsl_artifacts.py `
  --name custom-filter `
  --kernel-type Custom `
  --functions-file C:\Temp\custom_filter_functions.hlsl `
  --source-file C:\Temp\custom_filter_source.hlsl `
  --input-pin CustomInput:point `
  --output-pin CustomOut:point:CustomInput `
  --out-dir C:\Users\LiuYang\Desktop
```

Validate only:

```powershell
python .agents\skills\unreal-pcg-hlsl-node\scripts\validate_pcg_hlsl.py `
  --kernel-type PointGenerator `
  --code-file C:\Temp\pcg_building_scatter.hlsl
```

Extract code/spec hints from a copied PCG node export:

```powershell
python .agents\skills\unreal-pcg-hlsl-node\scripts\extract_pcg_hlsl_export.py `
  --export-file C:\Users\LiuYang\Desktop\pcg\ custom.txt `
  --out-dir C:\Users\LiuYang\Desktop
```

## Output Contract

Default artifact names:

- `<name>_functions.md`: raw `Shader Functions` only.
- `<name>_source.md`: raw `Shader Source` only.
- `<name>_pcg_node_paste.md`: paste-ready Unreal PCG node export with pins and both HLSL fields populated.
- `<name>_pcg_node_spec.json`: machine-readable kernel/pin/parameter summary.

The three `.md` files must contain raw code/export text only: no headings, instructions, or code fences. Never place an executable `Main()` only in `Shader Functions` while leaving `Shader Source` empty.

Pin syntax is `Name:Type[:InitFrom]`. Supported types are `point`, `param`, `landscape`, `virtualtexture`, and `texture2d`. `InitFrom` names the input used to initialize an output, for example `Out:point:In`.

Return the complete absolute path of every generated artifact. Tell the user to open `<name>_pcg_node_paste.md`, select all, copy, and paste into the PCG graph. Do not paste long HLSL into chat unless explicitly requested.

## PCG HLSL Rules

- Keep code GPU-friendly: deterministic math, bounded loops, no CPU-only assumptions, no silent fallback.
- Prefer explicit point fields and attributes; do not hide required graph parameters in magic constants unless it is a smoke test.
- Use stable parameter names such as `NumElements`, `Seed`, `VoxelSize`, `BoundsMin`, `BoundsMax`, `Spacing`, `Radius`, `Height`, `Density`.
- For generator kernels, always state how `ElementIndex` maps to generated position/seed.
- For processor kernels, state whether point count and metadata are preserved.
- State exactly what goes into `Shader Functions` versus `Shader Source`; a non-empty functions field does not make the kernel body execute.
- For `Custom`, explicitly list which pins initialize output data and whether output count equals input count.
- Do not claim Unreal validation unless the graph was compiled/run in the project and logs were checked.

## References

Read `references/pcg-hlsl-node-guide.md` when choosing a kernel type, documenting node settings, or explaining GPU PCG tradeoffs.

Read `references/pcg-hlsl-paste-export.md` when changing paste/export generation or comparing against copied nodes from the Editor.
