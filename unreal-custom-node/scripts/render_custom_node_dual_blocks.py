#!/usr/bin/env python3
"""
Render a final two-block Custom Node response:
1. HLSL code body
2. Unreal Material Editor paste export block

This is a convenience wrapper around generate_custom_node_paste_export.py so
the skill can consistently produce two copyable code fences.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import generate_custom_node_paste_export as paste_export


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render HLSL + Material Editor Paste Export as two markdown code blocks."
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
    parser.add_argument("--node-pos-x", type=int, default=0, help="Node X position. Default: 0")
    parser.add_argument("--node-pos-y", type=int, default=0, help="Node Y position. Default: 0")
    parser.add_argument(
        "--graph-node-name",
        default="MaterialGraphNode_Custom_1",
        help="Graph node object name. Default: MaterialGraphNode_Custom_1",
    )
    parser.add_argument(
        "--expression-name",
        default="MaterialExpressionCustom_1",
        help="Expression object name. Default: MaterialExpressionCustom_1",
    )
    parser.add_argument(
        "--seed",
        default="unreal-custom-node-export",
        help="Stable seed used to derive deterministic GUIDs. Default: unreal-custom-node-export",
    )
    parser.add_argument("--show-code", action="store_true", help="Emit ShowCode=True in the paste export.")
    parser.add_argument(
        "--output-file",
        help="Optional path to save the final markdown. Defaults to stdout.",
    )
    return parser.parse_args()


def render_markdown(args: argparse.Namespace) -> str:
    code_path = Path(args.code_file)
    code = paste_export.read_code(code_path)
    main_output_type = paste_export.normalize_output_type(args.output_type)
    inputs = paste_export.parse_inputs(args.input)
    additional_outputs = paste_export.parse_additional_outputs(args.additional_output)
    defines = paste_export.parse_defines(args.define)
    graph_node_name = paste_export.normalize_name(args.graph_node_name, "graph node name")
    expression_name = paste_export.normalize_name(args.expression_name, "expression name")

    export_text = paste_export.build_export_text(
        code=code,
        main_output_type=main_output_type,
        inputs=inputs,
        additional_outputs=additional_outputs,
        defines=defines,
        desc=args.desc,
        node_pos_x=args.node_pos_x,
        node_pos_y=args.node_pos_y,
        graph_node_name=graph_node_name,
        expression_name=expression_name,
        seed=args.seed,
        show_code=args.show_code,
    )

    return (
        "```hlsl\n"
        f"{code.rstrip()}\n"
        "```\n\n"
        "```text\n"
        f"{export_text.rstrip()}\n"
        "```\n"
    )


def main() -> int:
    args = parse_args()
    markdown = render_markdown(args)
    if args.output_file:
        Path(args.output_file).write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
