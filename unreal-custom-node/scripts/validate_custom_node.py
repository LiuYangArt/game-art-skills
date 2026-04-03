#!/usr/bin/env python3
"""
Static validator for Unreal Engine Custom Node HLSL snippets.

This script does not perform a full Unreal material compile. It wraps the
Custom Node body into a small HLSL shader, runs basic lint checks, and uses
DXC for offline syntax validation when available.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


OUTPUT_TYPE_ALIASES = {
    "float": "float",
    "float1": "float",
    "materialfloat": "float",
    "materialfloat1": "float",
    "cmot float1": "float",
    "cmot float": "float",
    "float2": "float2",
    "materialfloat2": "float2",
    "cmot float2": "float2",
    "float3": "float3",
    "materialfloat3": "float3",
    "cmot float3": "float3",
    "float4": "float4",
    "materialfloat4": "float4",
    "cmot float4": "float4",
}

INPUT_TYPE_ALIASES = {
    "float": "float",
    "float1": "float",
    "materialfloat": "float",
    "int": "int",
    "bool": "bool",
    "float2": "float2",
    "materialfloat2": "float2",
    "float3": "float3",
    "materialfloat3": "float3",
    "float4": "float4",
    "materialfloat4": "float4",
    "texture2d": "texture2d",
    "texture": "texture2d",
    "textureobject": "texture2d",
    "textureobject2d": "texture2d",
}


@dataclass
class InputSpec:
    name: str
    type_name: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Unreal Engine Custom Node code with lint + offline DXC compile."
    )
    parser.add_argument("--code-file", required=True, help="Path to the Custom Node code body file.")
    parser.add_argument(
        "--output-type",
        required=True,
        help="Output type such as float, float2, float3, float4, or CMOT Float3.",
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Input declaration in the form Name:Type. Repeat for multiple inputs.",
    )
    parser.add_argument(
        "--additional-output",
        action="append",
        default=[],
        help="Additional output declaration in the form Name:Type. Repeat for multiple outputs.",
    )
    parser.add_argument(
        "--define",
        action="append",
        default=[],
        help="Additional define in KEY or KEY=VALUE form. Repeatable.",
    )
    parser.add_argument(
        "--include-path",
        action="append",
        default=[],
        help="Additional include directory. Repeatable.",
    )
    parser.add_argument(
        "--shader-model",
        default="ps_6_0",
        help="DXC target profile. Default: ps_6_0",
    )
    parser.add_argument(
        "--entrypoint",
        default="mainPS",
        help="Temporary shader entrypoint name. Default: mainPS",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep the generated wrapper file for inspection.",
    )
    return parser.parse_args()


def normalize_output_type(raw: str) -> str:
    key = raw.strip().lower()
    key = key.replace("_", " ")
    key = re.sub(r"\s+", " ", key)
    normalized = OUTPUT_TYPE_ALIASES.get(key)
    if normalized:
        return normalized
    raise ValueError(f"Unsupported output type: {raw}")


def normalize_input_type(raw: str) -> str:
    key = raw.strip().lower()
    key = key.replace("_", "")
    normalized = INPUT_TYPE_ALIASES.get(key)
    if normalized:
        return normalized
    raise ValueError(f"Unsupported input type: {raw}")


def parse_input_specs(values: list[str]) -> list[InputSpec]:
    specs: list[InputSpec] = []
    for value in values:
        if ":" not in value:
            raise ValueError(f"Invalid --input value: {value}. Expected Name:Type")
        name, raw_type = value.split(":", 1)
        name = name.strip()
        if not name or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"Invalid input name: {name!r}")
        specs.append(InputSpec(name=name, type_name=normalize_input_type(raw_type)))
    return specs


def parse_additional_output_specs(values: list[str]) -> list[InputSpec]:
    specs: list[InputSpec] = []
    for value in values:
        if ":" not in value:
            raise ValueError(f"Invalid --additional-output value: {value}. Expected Name:Type")
        name, raw_type = value.split(":", 1)
        name = name.strip()
        if not name or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"Invalid additional output name: {name!r}")
        specs.append(InputSpec(name=name, type_name=normalize_output_type(raw_type)))
    return specs


def read_code(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Code file not found: {path}")
    return path.read_text(encoding="utf-8")


def lint_code(code: str, inputs: list[InputSpec], include_paths: list[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not code.strip():
        errors.append("Code is empty.")

    if code.count("{") != code.count("}"):
        errors.append("Brace count does not match.")

    if "return" not in code:
        warnings.append("No explicit return found. Unreal Custom Node bodies are safer with an explicit return.")

    if re.search(r"\b(float|half|int|bool|MaterialFloat[1-4]?)\s+\w+\s*\([^;]*\)\s*\{", code):
        warnings.append(
            "Detected a possible function definition inside the code body. Unreal Custom Node usually prefers inline code bodies."
        )

    if re.search(r"\b(float|half|int|bool)\s+\w+\s*\[[^\]]+\]", code):
        warnings.append("Detected a possible array declaration. Official docs note that arrays are not supported.")

    if "#include" in code and not include_paths:
        warnings.append("Code contains #include but no --include-path was provided.")

    texture_inputs = {item.name for item in inputs if item.type_name == "texture2d"}
    uses_texture_sample = "Texture2DSample(" in code or "TextureCubeSample(" in code
    if uses_texture_sample and not texture_inputs:
        warnings.append("Texture sampling macro detected, but no texture2d input was declared.")

    risky_names = {"Time", "Parameters", "Material", "View", "Primitive"}
    colliding = sorted(item.name for item in inputs if item.name in risky_names)
    if colliding:
        warnings.append(
            "Some input names are high-risk for collisions inside Unreal material compilation: "
            + ", ".join(colliding)
        )

    return errors, warnings


def find_dxc() -> str | None:
    direct = shutil.which("dxc.exe")
    if direct:
        return direct

    search_roots = [
        Path(r"C:\Program Files (x86)\Windows Kits\10\bin"),
        Path(r"C:\Program Files (x86)\Windows Kits\10\Redist\D3D"),
    ]
    candidates: list[Path] = []
    for root in search_roots:
        if root.exists():
            candidates.extend(root.rglob("dxc.exe"))
    if not candidates:
        return None

    def rank(path: Path) -> tuple[int, str]:
        score = 1 if "x64" in str(path).lower() else 0
        return (score, str(path))

    candidates.sort(key=rank, reverse=True)
    return str(candidates[0])


def default_literal(type_name: str) -> str:
    if type_name == "float":
        return "0.5"
    if type_name == "int":
        return "1"
    if type_name == "bool":
        return "true"
    if type_name == "float2":
        return "float2(0.5, 0.5)"
    if type_name == "float3":
        return "float3(0.5, 0.5, 0.5)"
    if type_name == "float4":
        return "float4(0.5, 0.5, 0.5, 1.0)"
    raise ValueError(f"No default literal for type: {type_name}")


def output_to_float4_expr(output_type: str, value_name: str) -> str:
    if output_type == "float":
        return f"float4({value_name}, {value_name}, {value_name}, {value_name})"
    if output_type == "float2":
        return f"float4({value_name}, 0.0, 1.0)"
    if output_type == "float3":
        return f"float4({value_name}, 1.0)"
    if output_type == "float4":
        return value_name
    raise ValueError(f"Unsupported output type: {output_type}")


def build_wrapper(
    code: str,
    output_type: str,
    inputs: list[InputSpec],
    additional_outputs: list[InputSpec],
    entrypoint: str,
) -> str:
    scalar_inputs = [item for item in inputs if item.type_name != "texture2d"]
    texture_inputs = [item for item in inputs if item.type_name == "texture2d"]

    global_decls = []
    for item in texture_inputs:
        global_decls.append(f"Texture2D {item.name};")
        global_decls.append(f"SamplerState {item.name}Sampler;")

    param_list = ", ".join(f"{item.type_name} {item.name}" for item in scalar_inputs)
    if not param_list:
        param_list = "float DummyInput"

    call_args = ", ".join(default_literal(item.type_name) for item in scalar_inputs)
    if not call_args:
        call_args = "0.0"

    float4_expr = output_to_float4_expr(output_type, "result")
    additional_output_locals = [
        f"{item.type_name} {item.name} = {default_literal(item.type_name)};"
        for item in additional_outputs
    ]

    return f"""#define MaterialFloat float
#define MaterialFloat2 float2
#define MaterialFloat3 float3
#define MaterialFloat4 float4

#ifndef Texture2DSample
#define Texture2DSample(T, S, UV) T.Sample(S, UV)
#endif

#ifndef Texture2DSampleLevel
#define Texture2DSampleLevel(T, S, UV, L) T.SampleLevel(S, UV, L)
#endif

#ifndef TextureCubeSample
#define TextureCubeSample(T, S, DIR) T.Sample(S, DIR)
#endif

{os.linesep.join(global_decls)}

{output_type} CustomExpressionEntry({param_list})
{{
{indent_block(os.linesep.join(additional_output_locals)) if additional_output_locals else ""}
{indent_block(code.rstrip())}
}}

float4 {entrypoint}(float4 position : SV_Position) : SV_Target
{{
    {output_type} result = CustomExpressionEntry({call_args});
    return {float4_expr};
}}
"""


def indent_block(code: str, spaces: int = 4) -> str:
    indent = " " * spaces
    return "\n".join(indent + line if line else "" for line in code.splitlines())


def run_dxc(
    dxc_path: str,
    wrapper_path: Path,
    entrypoint: str,
    shader_model: str,
    defines: list[str],
    include_paths: list[str],
) -> tuple[int, str]:
    output_path = wrapper_path.with_suffix(".dxil")
    command = [
        dxc_path,
        "-nologo",
        "-E",
        entrypoint,
        "-T",
        shader_model,
        "-Fo",
        str(output_path),
        str(wrapper_path),
    ]

    for item in defines:
        command.extend(["-D", item])
    for item in include_paths:
        command.extend(["-I", item])

    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (process.stdout or "") + (process.stderr or "")
    return process.returncode, output


def main() -> int:
    args = parse_args()

    try:
        code_path = Path(args.code_file)
        code = read_code(code_path)
        output_type = normalize_output_type(args.output_type)
        inputs = parse_input_specs(args.input)
        additional_outputs = parse_additional_output_specs(args.additional_output)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 2

    errors, warnings = lint_code(code, inputs, args.include_path)
    for item in warnings:
        print(f"[WARN] {item}")
    if errors:
        for item in errors:
            print(f"[ERROR] {item}")
        return 1

    dxc_path = find_dxc()
    if not dxc_path:
        print("[ERROR] Could not find dxc.exe. Install Windows SDK or add dxc.exe to PATH.")
        return 2

    temp_dir_ctx = tempfile.TemporaryDirectory()
    temp_dir = Path(temp_dir_ctx.name)
    wrapper_path = temp_dir / "custom_node_wrapper.hlsl"

    wrapper = build_wrapper(code, output_type, inputs, additional_outputs, args.entrypoint)
    wrapper_path.write_text(wrapper, encoding="utf-8")

    print(f"[INFO] Using dxc: {dxc_path}")
    print(f"[INFO] Wrapper: {wrapper_path}")

    exit_code, compile_output = run_dxc(
        dxc_path=dxc_path,
        wrapper_path=wrapper_path,
        entrypoint=args.entrypoint,
        shader_model=args.shader_model,
        defines=args.define,
        include_paths=args.include_path,
    )

    if compile_output.strip():
        print(compile_output.strip())

    if exit_code == 0:
        print("[OK] DXC offline compile succeeded.")
        if args.keep_temp:
            preserved = code_path.parent / f"{code_path.stem}.wrapped.hlsl"
            preserved.write_text(wrapper, encoding="utf-8")
            print(f"[INFO] Preserved wrapper at: {preserved}")
        else:
            temp_dir_ctx.cleanup()
        return 0

    print("[ERROR] DXC offline compile failed.")
    if args.keep_temp:
        preserved = code_path.parent / f"{code_path.stem}.wrapped.hlsl"
        preserved.write_text(wrapper, encoding="utf-8")
        print(f"[INFO] Preserved wrapper at: {preserved}")
    else:
        temp_dir_ctx.cleanup()
    return 1


if __name__ == "__main__":
    sys.exit(main())
