#!/usr/bin/env python3
"""
Generate a Unreal Material Editor copy/paste text block for a Custom Node.

This script focuses on a stable, pasteable export snippet for a single
MaterialGraphNode_Custom / MaterialExpressionCustom node. It does not attempt
to auto-generate and wire the surrounding parameter nodes yet.
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path


OUTPUT_TYPE_ALIASES = {
    "float": "CMOT_Float1",
    "float1": "CMOT_Float1",
    "materialfloat": "CMOT_Float1",
    "materialfloat1": "CMOT_Float1",
    "cmot float": "CMOT_Float1",
    "cmot float1": "CMOT_Float1",
    "cmot_float": "CMOT_Float1",
    "cmot_float1": "CMOT_Float1",
    "float2": "CMOT_Float2",
    "materialfloat2": "CMOT_Float2",
    "cmot float2": "CMOT_Float2",
    "cmot_float2": "CMOT_Float2",
    "float3": "CMOT_Float3",
    "materialfloat3": "CMOT_Float3",
    "cmot float3": "CMOT_Float3",
    "cmot_float3": "CMOT_Float3",
    "float4": "CMOT_Float4",
    "materialfloat4": "CMOT_Float4",
    "cmot float4": "CMOT_Float4",
    "cmot_float4": "CMOT_Float4",
    "materialattributes": "CMOT_MaterialAttributes",
    "material_attributes": "CMOT_MaterialAttributes",
    "cmot materialattributes": "CMOT_MaterialAttributes",
    "cmot_materialattributes": "CMOT_MaterialAttributes",
}


@dataclass
class NamedOutput:
    name: str
    output_type: str


@dataclass
class DefineSpec:
    name: str
    value: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a UE Material Editor copy/paste export block for a Custom Node."
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
    parser.add_argument(
        "--define",
        action="append",
        default=[],
        help="Additional define in KEY or KEY=VALUE form. Repeatable.",
    )
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
    parser.add_argument(
        "--show-code",
        action="store_true",
        help="Emit ShowCode=True. Recommended when you want the node to open with code visible.",
    )
    parser.add_argument(
        "--output-file",
        help="Optional path to save the generated export text. Defaults to stdout.",
    )
    return parser.parse_args()


def read_code(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Code file not found: {path}")
    return path.read_text(encoding="utf-8")


def normalize_output_type(raw: str) -> str:
    key = raw.strip().lower().replace("_", " ")
    key = re.sub(r"\s+", " ", key)
    output_type = OUTPUT_TYPE_ALIASES.get(key)
    if not output_type:
        raise ValueError(f"Unsupported output type: {raw}")
    return output_type


def normalize_name(name: str, label: str) -> str:
    value = name.strip()
    if not value:
        raise ValueError(f"{label} cannot be empty")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


def parse_inputs(values: list[str]) -> list[str]:
    return [normalize_name(value, "input name") for value in values]


def parse_additional_outputs(values: list[str]) -> list[NamedOutput]:
    outputs: list[NamedOutput] = []
    for value in values:
        if ":" not in value:
            raise ValueError(f"Invalid --additional-output value: {value}. Expected Name:Type")
        name, type_name = value.split(":", 1)
        outputs.append(
            NamedOutput(
                name=normalize_name(name, "additional output name"),
                output_type=normalize_output_type(type_name),
            )
        )
    return outputs


def parse_defines(values: list[str]) -> list[DefineSpec]:
    defines: list[DefineSpec] = []
    for value in values:
        if "=" in value:
            name, define_value = value.split("=", 1)
            defines.append(DefineSpec(name=normalize_name(name, "define name"), value=define_value))
        else:
            defines.append(DefineSpec(name=normalize_name(value, "define name"), value=None))
    return defines


def stable_hex(seed: str, label: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}:{label}").hex.upper()


def escape_export_string(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\\", "\\\\").replace('"', '\\"')
    normalized = normalized.replace("\n", "\\r\\n")
    return normalized


def format_additional_output(index: int, item: NamedOutput) -> str:
    return f'      AdditionalOutputs({index})=(OutputName="{item.name}",OutputType={item.output_type})'


def format_define(index: int, item: DefineSpec) -> str:
    if item.value is None:
        return f'      AdditionalDefines({index})=(DefineName="{item.name}")'
    return (
        f'      AdditionalDefines({index})='
        f'(DefineName="{item.name}",DefineValue="{escape_export_string(item.value)}")'
    )


def format_linked_to_clause(linked_to: list[tuple[str, str]] | None) -> str:
    if not linked_to:
        return ""
    linked_text = ",".join(f"{node} {pin}" for node, pin in linked_to)
    return f"LinkedTo=({linked_text},),"


def build_pin_lines(
    seed: str,
    inputs: list[str],
    additional_outputs: list[NamedOutput],
    input_links: dict[str, list[tuple[str, str]]] | None = None,
    output_links: dict[str, list[tuple[str, str]]] | None = None,
) -> list[str]:
    lines: list[str] = []
    for index, input_name in enumerate(inputs):
        pin_id = stable_hex(seed, f"pin:input:{index}:{input_name}")
        link_clause = format_linked_to_clause((input_links or {}).get(input_name))
        lines.append(
            '   CustomProperties Pin '
            f'(PinId={pin_id},PinName="{input_name}",PinType.PinCategory="required",'
            'PinType.PinSubCategory="",PinType.PinSubCategoryObject=None,'
            'PinType.PinSubCategoryMemberReference=(),PinType.PinValueType=(),'
            'PinType.ContainerType=None,PinType.bIsReference=False,PinType.bIsConst=False,'
            'PinType.bIsWeakPointer=False,PinType.bIsUObjectWrapper=False,'
            'PinType.bSerializeAsSinglePrecisionFloat=False,'
            f'{link_clause}'
            'PersistentGuid=00000000000000000000000000000000,bHidden=False,'
            'bNotConnectable=False,bDefaultValueIsReadOnly=False,bDefaultValueIsIgnored=False,'
            'bAdvancedView=False,bOrphanedPin=False,)'
        )

    return_pin_id = stable_hex(seed, "pin:output:return")
    return_link_clause = format_linked_to_clause((output_links or {}).get("return"))
    lines.append(
        '   CustomProperties Pin '
        f'(PinId={return_pin_id},PinName="return",Direction="EGPD_Output",'
        'PinType.PinCategory="",PinType.PinSubCategory="",PinType.PinSubCategoryObject=None,'
        'PinType.PinSubCategoryMemberReference=(),PinType.PinValueType=(),'
        'PinType.ContainerType=None,PinType.bIsReference=False,PinType.bIsConst=False,'
        'PinType.bIsWeakPointer=False,PinType.bIsUObjectWrapper=False,'
        'PinType.bSerializeAsSinglePrecisionFloat=False,'
        f'{return_link_clause}'
        'PersistentGuid=00000000000000000000000000000000,bHidden=False,'
        'bNotConnectable=False,bDefaultValueIsReadOnly=False,bDefaultValueIsIgnored=False,'
        'bAdvancedView=False,bOrphanedPin=False,)'
    )

    for index, item in enumerate(additional_outputs):
        pin_id = stable_hex(seed, f"pin:output:{index}:{item.name}")
        link_clause = format_linked_to_clause((output_links or {}).get(item.name))
        lines.append(
            '   CustomProperties Pin '
            f'(PinId={pin_id},PinName="{item.name}",Direction="EGPD_Output",'
            'PinType.PinCategory="",PinType.PinSubCategory="",PinType.PinSubCategoryObject=None,'
            'PinType.PinSubCategoryMemberReference=(),PinType.PinValueType=(),'
            'PinType.ContainerType=None,PinType.bIsReference=False,PinType.bIsConst=False,'
            'PinType.bIsWeakPointer=False,PinType.bIsUObjectWrapper=False,'
            'PinType.bSerializeAsSinglePrecisionFloat=False,'
            f'{link_clause}'
            'PersistentGuid=00000000000000000000000000000000,bHidden=False,'
            'bNotConnectable=False,bDefaultValueIsReadOnly=False,bDefaultValueIsIgnored=False,'
            'bAdvancedView=False,bOrphanedPin=False,)'
        )
    return lines


def build_export_text(
    *,
    code: str,
    main_output_type: str,
    inputs: list[str],
    additional_outputs: list[NamedOutput],
    defines: list[DefineSpec],
    desc: str,
    node_pos_x: int,
    node_pos_y: int,
    graph_node_name: str,
    expression_name: str,
    seed: str,
    show_code: bool,
    input_links: dict[str, list[tuple[str, str]]] | None = None,
    output_links: dict[str, list[tuple[str, str]]] | None = None,
) -> str:
    material_expression_guid = stable_hex(seed, "material_expression_guid")
    node_guid = stable_hex(seed, "node_guid")
    escaped_code = escape_export_string(code)

    lines: list[str] = [
        f'Begin Object Class=/Script/UnrealEd.MaterialGraphNode_Custom Name="{graph_node_name}"',
        f'   Begin Object Class=/Script/Engine.MaterialExpressionCustom Name="{expression_name}"',
        "   End Object",
        f'   Begin Object Name="{expression_name}"',
        f'      Code="{escaped_code}"',
        f"      OutputType={main_output_type}",
    ]

    if desc:
        lines.append(f'      Description="{escape_export_string(desc)}"')

    for index, input_name in enumerate(inputs):
        lines.append(f'      Inputs({index})=(InputName="{input_name}")')

    for index, item in enumerate(additional_outputs):
        lines.append(format_additional_output(index, item))

    for index, item in enumerate(defines):
        lines.append(format_define(index, item))

    if show_code:
        lines.append("      ShowCode=True")

    lines.extend(
        [
            f"      MaterialExpressionEditorX={node_pos_x}",
            f"      MaterialExpressionEditorY={node_pos_y}",
            f"      MaterialExpressionGuid={material_expression_guid}",
            "      bShowOutputNameOnPin=True",
            '      Outputs(0)=(OutputName="return")',
        ]
    )

    for index, item in enumerate(additional_outputs, start=1):
        lines.append(f'      Outputs({index})=(OutputName="{item.name}")')

    lines.extend(
        [
            "   End Object",
            f'   MaterialExpression=/Script/Engine.MaterialExpressionCustom\'{expression_name}\'',
            f"   NodePosX={node_pos_x}",
            f"   NodePosY={node_pos_y}",
            f"   NodeGuid={node_guid}",
        ]
    )

    lines.extend(build_pin_lines(seed, inputs, additional_outputs, input_links, output_links))
    lines.append("End Object")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    code = read_code(Path(args.code_file))
    main_output_type = normalize_output_type(args.output_type)
    inputs = parse_inputs(args.input)
    additional_outputs = parse_additional_outputs(args.additional_output)
    defines = parse_defines(args.define)
    graph_node_name = normalize_name(args.graph_node_name, "graph node name")
    expression_name = normalize_name(args.expression_name, "expression name")

    export_text = build_export_text(
        code=code,
        main_output_type=main_output_type,
        inputs=inputs,
        additional_outputs=additional_outputs,
        input_links=None,
        output_links=None,
        defines=defines,
        desc=args.desc,
        node_pos_x=args.node_pos_x,
        node_pos_y=args.node_pos_y,
        graph_node_name=graph_node_name,
        expression_name=expression_name,
        seed=args.seed,
        show_code=args.show_code,
    )

    if args.output_file:
        Path(args.output_file).write_text(export_text, encoding="utf-8")
    else:
        sys.stdout.write(export_text)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
