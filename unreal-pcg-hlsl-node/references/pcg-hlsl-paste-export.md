# PCG HLSL Paste Export Notes

## Observed Export Patterns

Copied PCG Custom HLSL nodes are Unreal text exports rooted at:

```text
Begin Object Class=/Script/PCGEditor.PCGEditorGraphNode Name="PCGEditorGraphNode_0"
```

The node contains:

- `/Script/PCG.PCGNode`
- `/Script/PCG.PCGCustomHLSLSettings`
- several `/Script/PCG.PCGPin` objects
- `KernelType=...`
- `ShaderFunctions="...escaped HLSL..."`
- `ShaderSource="...escaped executable body..."` when the node has an authored kernel body
- `CachedOverridableParams` for `NumElements`, `ThreadCountMultiplier`, `FixedThreadCount`, and `Seed`
- editor `CustomProperties Pin` entries

## Samples From This Workspace

`pcg custom.txt` shows:

- `KernelType=Custom`
- extra point input pin `CustomInput`
- extra point output pin `CustomOut`
- default `In`, advanced override pins, `Out`
- the observed legacy sample stores HLSL in `ShaderFunctions`, but this is insufficient evidence that executable processor logic belongs there

`pcg point gen.txt` shows:

- `KernelType=PointGenerator`
- `InputPins=` on settings
- no required `In` point pin
- advanced override pins and a single point `Out` pin

## Script Policy

`emit_pcg_hlsl_artifacts.py` generates deterministic UE 5.7 paste text from separate functions/source files. It creates the requested settings pins, editor pins, output initialization links, overridable pins, and preserves both HLSL fields.

For UE 5.7 preset kernels, do not leave `Shader Source` empty. Split helper code into `Shader Functions` and per-thread statements into `Shader Source`. A generated artifact is paste-ready only after the script's structural checks confirm both fields and all requested pins are present.

The generated paste file intentionally includes only raw export text. Do not add Markdown headings, code fences, or usage notes inside `*_pcg_node_paste.md`.
