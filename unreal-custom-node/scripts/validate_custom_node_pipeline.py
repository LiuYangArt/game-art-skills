#!/usr/bin/env python3
"""
Two-layer validation for Unreal Custom Node code.

Layer 1:
- Static lint + offline DXC compile via validate_custom_node.py

Layer 2 (optional):
- Unreal project validation via UnrealEditor-Cmd + Python probe
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Unreal Custom Node code with DXC first, then optional in-project Unreal validation."
    )
    parser.add_argument("--code-file", required=True, help="Path to the Custom Node code body file.")
    parser.add_argument("--output-type", required=True, help="Custom Node output type, e.g. float3 or CMOT Float3.")
    parser.add_argument("--input", action="append", default=[], help="Input declaration in the form Name:Type. Repeatable.")
    parser.add_argument("--define", action="append", default=[], help="Additional define in KEY or KEY=VALUE form.")
    parser.add_argument("--include-path", action="append", default=[], help="Additional include path. Repeatable.")
    parser.add_argument("--shader-model", default="ps_6_0", help="DXC shader model. Default: ps_6_0")
    parser.add_argument("--entrypoint", default="mainPS", help="Temporary DXC entrypoint. Default: mainPS")
    parser.add_argument("--keep-temp", action="store_true", help="Preserve wrapped HLSL files for inspection.")

    parser.add_argument("--project", help="Optional .uproject path for Unreal in-project validation.")
    parser.add_argument("--asset-path", help="Optional Unreal asset path, e.g. /Game/Developers/LiuYang/M_AI_WaterShader.M_AI_WaterShader")
    parser.add_argument("--engine-root", help="Optional Unreal engine root for in-project validation.")
    parser.add_argument("--engine-version", help="Optional Unreal version like 5.5 or 5.7 for in-project validation.")
    parser.add_argument("--nullrhi", action="store_true", help="Pass -NullRHI to UnrealEditor-Cmd during project validation.")
    parser.add_argument("--tail", type=int, default=120, help="Log tail line count for Unreal validation. Default: 120")
    return parser.parse_args()


def info(message: str) -> None:
    print(f"[INFO] {message}", flush=True)


def error(message: str) -> None:
    print(f"[ERROR] {message}", flush=True)


def run_command(command: list[str]) -> int:
    info("Running command:")
    print(" ".join(f'"{part}"' if " " in part else part for part in command), flush=True)
    process = subprocess.run(command)
    return process.returncode


def find_codex_skill_path(skill_name: str) -> Path:
    base = Path.home() / ".codex" / "skills" / skill_name
    if not base.exists():
        raise FileNotFoundError(f"Required skill not found: {base}")
    return base


def main() -> int:
    args = parse_args()

    skill_dir = Path(__file__).resolve().parent
    static_validator = skill_dir / "validate_custom_node.py"

    dxc_command = [
        sys.executable,
        str(static_validator),
        "--code-file",
        args.code_file,
        "--output-type",
        args.output_type,
        "--shader-model",
        args.shader_model,
        "--entrypoint",
        args.entrypoint,
    ]
    for item in args.input:
        dxc_command.extend(["--input", item])
    for item in args.define:
        dxc_command.extend(["--define", item])
    for item in args.include_path:
        dxc_command.extend(["--include-path", item])
    if args.keep_temp:
        dxc_command.append("--keep-temp")

    info("Layer 1/2: DXC static validation")
    dxc_exit = run_command(dxc_command)
    if dxc_exit != 0:
        error("Static validation failed. Skipping Unreal in-project validation.")
        return dxc_exit
    info("Layer 1/2 passed.")

    if not args.project or not args.asset_path:
        info("Layer 2/2 skipped. Provide both --project and --asset-path to run Unreal in-project validation.")
        return 0

    ue_skill_dir = find_codex_skill_path("unreal-editor-python-debug")
    ue_runner = ue_skill_dir / "scripts" / "run_ue_python_cmd.py"
    ue_probe = ue_skill_dir / "scripts" / "probe_asset.py"

    ue_command = [
        sys.executable,
        str(ue_runner),
        "--project",
        args.project,
        "--script",
        str(ue_probe),
        "--env",
        f"UE_ASSET_PATH={args.asset_path}",
        "--env",
        "UE_RECOMPILE_MATERIAL=1",
        "--env",
        "UE_PROPERTY_FILTER=compile",
        "--grep",
        "[CodexProbe]",
        "--grep",
        "MaterialEditorStats",
        "--grep",
        "error:",
        "--grep",
        "Shader debug info dumped",
        "--tail",
        str(args.tail),
        "--quiet-editor-output",
    ]
    if args.engine_root:
        ue_command.extend(["--engine-root", args.engine_root])
    if args.engine_version:
        ue_command.extend(["--engine-version", args.engine_version])
    if args.nullrhi:
        ue_command.append("--nullrhi")

    info("Layer 2/2: Unreal in-project validation")
    ue_exit = run_command(ue_command)
    if ue_exit == 0:
        info("Layer 2/2 passed.")
    return ue_exit


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        error(str(exc))
        sys.exit(2)
