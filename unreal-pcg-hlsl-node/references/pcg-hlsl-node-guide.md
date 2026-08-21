# PCG HLSL Node Guide

## Source Context

Based on Epic's UE PCG GPU processing documentation and copied PCG node exports from this workspace. The public documentation page is currently UE 5.8-oriented and GPU PCG is Beta there; verify exact fields in the active 5.7 AngelScript build before large graph changes.

## Kernel Types

| Kernel Type | Main Use | Cardinality | Use When |
| --- | --- | --- | --- |
| `PointProcessor` | Modify existing point data | Usually input point count = output point count | Offset/rotate/scale points, set density, compute attributes, cheap per-point filtering patterns. |
| `PointGenerator` | Create point data | Driven by `NumElements` / thread count | Procedural grids, random scatter, rings, lines, volume fills, smoke-test point sources. |
| `AttributeProcessor` | Modify Attribute Set data | Attribute rows, not points | Precompute numeric tables, convert parameter rows, build data for later PCG stages. |
| `Custom` | Manual GPU kernel layout | User-controlled | Multiple custom pins, nonstandard output, manual thread/output behavior, advanced algorithms. |

Default choice: use `PointProcessor` for existing points, `PointGenerator` for new points, and avoid `Custom` until the preset kernels are too limiting.

## Agent Decision Rule

Use HLSL when the hard part is math over many points. Use PCG graph nodes/MCP when the hard part is asset wiring, graph topology, editor validation, or mesh spawning. HLSL nodes make point logic faster to author and run on GPU, but they do not remove the need for PCG graph setup and runtime validation.

## Common Node Spec Fields

- `KernelType`: `PointProcessor`, `PointGenerator`, `AttributeProcessor`, or `Custom`.
- `ShaderFunctions`: copied exports in this project store HLSL text here. Keep generated code compatible with this field until the active engine proves otherwise.
- `NumElements`: important for generators and custom kernels with generated output.
- `ThreadCountMultiplier` / `FixedThreadCount`: advanced; leave defaults unless the user is optimizing dispatch.
- `Seed`: expose or document deterministic random behavior.
- `InputPins` / `OutputPins`: required for `Custom`; generated defaults are usually enough for preset kernels.

## Recommended HLSL Shape

UE's Custom HLSL editor separates reusable helpers from the executable body:

- `Shader Functions`: constants and helper functions. A `Main()` placed only here is merely declared as a helper and is not automatically invoked.
- `Shader Source`: statements inserted into the engine-generated kernel body and executed once per dispatched thread. Preset kernels already inject per-thread symbols such as `ThreadIndex`, `ElementIndex`, and input/output data indices.

Keep random helpers deterministic and seedable. Put helpers such as the following in `Shader Functions`:

```hlsl
uint Hash(uint x)
{
    x ^= x >> 16;
    x *= 0x7feb352d;
    x ^= x >> 15;
    x *= 0x846ca68b;
    x ^= x >> 16;
    return x;
}

float Rand01(uint x)
{
    return (Hash(x) & 0x00FFFFFF) / 16777215.0;
}
```

For generator kernels, document the expected entry parameters, usually including `ElementIndex`, `Seed`, and output point fields such as `Position` and `Density`.

For processor kernels, preserve existing data unless the requested behavior requires changing it.

For preset processor/generator nodes, place the actual reads, writes, and filtering statements in `Shader Source` without a `Main()` wrapper. After pasting, verify that `Shader Source` is visibly non-empty before debugging graph behavior.

## Validation Boundaries

`validate_pcg_hlsl.py` only checks basic static issues: braces, entry function, suspicious unsupported syntax, and kernel/spec consistency. Unreal-specific symbols, generated wrappers, pin binding, and shader compilation must be verified in the Editor or via commandlet/logs.

After applying to a graph, run the smallest meaningful validation:

1. Save/compile the PCG graph or asset.
2. Clear PCG output if cached output could hide failure.
3. Run PCG on a known actor.
4. Inspect `Saved/Logs/Paralogue.log` for shader/PCG errors.
5. Compare point counts or bounds if the code is meant to affect generation density or extents.
6. Use an intentionally impossible threshold or unconditional `Out_RemovePoint(...)` smoke test when uncertain whether the source body executes; the downstream point count should collapse.
