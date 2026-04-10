#!/usr/bin/env python3
"""
Emit split markdown artifacts for Unreal Custom Node workflows.

Default workflow:
- always write a HLSL markdown file
- always write a single-node paste export markdown file
- always write a full-graph export markdown file

The script prints absolute output paths so the caller can forward them to the
user without relying on app-specific clickable links.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import generate_custom_node_full_graph_export as full_graph_export
import generate_custom_node_paste_export as paste_export


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emit split markdown artifacts for Unreal Custom Node outputs."
    )
    parser.add_argument("--code-file", required=True, help="Path to the Custom Node code body file.")
    parser.add_argument("--output-type", required=True, help="Main output type, e.g. float3.")
    parser.add_argument("--input", action="append", default=[], help="Input pin name. Repeatable.")
    parser.add_argument(
        "--additional-output",
        action="append",
        default=[],
        help="Additional output in the form Name:Type. Repeatable.",
    )
    parser.add_argument("--define", action="append", default=[], help="Additional define in KEY or KEY=VALUE form.")
    parser.add_argument("--desc", default="", help="Optional node description.")
    parser.add_argument("--seed", default="unreal-custom-node-artifacts", help="Stable seed for generated ids.")
    parser.add_argument("--base-name", required=True, help="Base file name without extension.")
    parser.add_argument("--output-dir", required=True, help="Directory to write markdown artifacts into.")
    parser.add_argument("--node-pos-x", type=int, default=0, help="Node X position for paste export.")
    parser.add_argument("--node-pos-y", type=int, default=0, help="Node Y position for paste export.")
    parser.add_argument(
        "--graph-node-name",
        default="MaterialGraphNode_Custom_1",
        help="Graph node object name for single-node paste export.",
    )
    parser.add_argument(
        "--expression-name",
        default="MaterialExpressionCustom_1",
        help="Expression object name for single-node paste export.",
    )
    parser.add_argument(
        "--layout-file",
        help="Optional layout JSON for full-graph export. Defaults to a custom-node-only layout when omitted.",
    )
    return parser.parse_args()


def ensure_parent_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_hlsl_markdown(code: str, output_path: Path) -> None:
    output_path.write_text(code.rstrip() + "\n", encoding="utf-8")


def write_paste_markdown(
    *,
    code: str,
    args: argparse.Namespace,
    output_path: Path,
) -> None:
    export_text = paste_export.build_export_text(
        code=code,
        main_output_type=paste_export.normalize_output_type(args.output_type),
        inputs=paste_export.parse_inputs(args.input),
        additional_outputs=paste_export.parse_additional_outputs(args.additional_output),
        defines=paste_export.parse_defines(args.define),
        desc=args.desc,
        node_pos_x=args.node_pos_x,
        node_pos_y=args.node_pos_y,
        graph_node_name=paste_export.normalize_name(args.graph_node_name, "graph node name"),
        expression_name=paste_export.normalize_name(args.expression_name, "expression name"),
        seed=args.seed,
        show_code=True,
    )
    output_path.write_text(export_text.rstrip() + "\n", encoding="utf-8")


def write_full_graph_markdown(args: argparse.Namespace, output_path: Path) -> None:
    export_text = full_graph_export.build_full_graph_export(args)
    output_path.write_text(export_text.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    code_path = Path(args.code_file)
    if not code_path.exists():
        raise FileNotFoundError(f"Code file not found: {code_path}")

    output_dir = Path(args.output_dir).expanduser().resolve()
    ensure_parent_dir(output_dir)

    code = paste_export.read_code(code_path)
    hlsl_path = output_dir / f"{args.base_name}_custom_node_hlsl.md"
    write_hlsl_markdown(code, hlsl_path)

    output_paths = [hlsl_path.resolve()]

    paste_path = output_dir / f"{args.base_name}_custom_node_paste.md"
    write_paste_markdown(code=code, args=args, output_path=paste_path)
    output_paths.append(paste_path.resolve())

    full_graph_path = output_dir / f"{args.base_name}_full_graph.md"
    write_full_graph_markdown(args, full_graph_path)
    output_paths.append(full_graph_path.resolve())

    for path in output_paths:
        print(str(path))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
