#!/usr/bin/env python3
"""
Generate a fuller Unreal Material Editor copy/paste export block that includes:
- a Custom Node
- selected surrounding source nodes
- selected helper nodes
- LinkedTo connections

This first version focuses on a stable subset that matches common Custom Node
workflows:
- WorldPosition
- CameraPositionWS
- Time
- ScalarParameter
- Constant3Vector
- TextureCoordinate
- TextureObjectParameter
- MakeFloat3 material function call

It is intentionally template-driven rather than attempting to cover every
MaterialExpression type in Unreal.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

import generate_custom_node_paste_export as custom_export


def stable_hex(seed: str, label: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}:{label}").hex.upper()


def source_output_pin_id(seed: str, node_name: str) -> str:
    return stable_hex(seed, f"{node_name}:output")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a fuller Unreal Material Editor export block for a Custom Node and selected surrounding nodes."
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
    parser.add_argument("--desc", default="", help="Optional node description.")
    parser.add_argument("--seed", default="unreal-custom-node-full-graph", help="Stable seed for GUID generation.")
    parser.add_argument(
        "--layout-file",
        required=True,
        help="JSON file that describes surrounding nodes and connections.",
    )
    parser.add_argument("--output-file", help="Optional path to save export text.")
    return parser.parse_args()


def read_layout(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Layout file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def pin_line(
    *,
    pin_id: str,
    pin_name: str,
    direction: str | None = None,
    pin_category: str = "",
    pin_subcategory: str = "",
    linked_to: list[tuple[str, str]] | None = None,
    not_connectable: bool = False,
    default_value: str | None = None,
) -> str:
    parts = [f"PinId={pin_id}", f'PinName="{pin_name}"']
    if direction:
        parts.append(f'Direction="{direction}"')
    parts.append(f'PinType.PinCategory="{pin_category}"')
    parts.append(f'PinType.PinSubCategory="{pin_subcategory}"')
    parts.append("PinType.PinSubCategoryObject=None")
    parts.append("PinType.PinSubCategoryMemberReference=()")
    parts.append("PinType.PinValueType=()")
    parts.append("PinType.ContainerType=None")
    parts.append("PinType.bIsReference=False")
    parts.append("PinType.bIsConst=False")
    parts.append("PinType.bIsWeakPointer=False")
    parts.append("PinType.bIsUObjectWrapper=False")
    parts.append("PinType.bSerializeAsSinglePrecisionFloat=False")
    if linked_to:
        linked_text = ",".join(f"{node} {pin}" for node, pin in linked_to)
        parts.append(f"LinkedTo=({linked_text},)")
    if default_value is not None:
        parts.append(f'DefaultValue="{default_value}"')
    parts.append("PersistentGuid=00000000000000000000000000000000")
    parts.append("bHidden=False")
    parts.append(f"bNotConnectable={'True' if not_connectable else 'False'}")
    parts.append("bDefaultValueIsReadOnly=False")
    parts.append("bDefaultValueIsIgnored=False")
    parts.append("bAdvancedView=False")
    parts.append("bOrphanedPin=False")
    return "   CustomProperties Pin (" + ",".join(parts) + ",)"


def build_source_node(seed: str, spec: dict, target_graph_name: str, target_pin_id: str) -> str:
    source_type = spec["source_type"]
    node_name = spec["graph_node_name"]
    expr_name = spec["expression_name"]
    pos_x = spec["node_pos_x"]
    pos_y = spec["node_pos_y"]
    material_expression_guid = stable_hex(seed, f"{node_name}:material_expression_guid")
    node_guid = stable_hex(seed, f"{node_name}:node_guid")
    output_pin_id = source_output_pin_id(seed, node_name)

    if source_type == "world_position":
        return "\n".join(
            [
                f'Begin Object Class=/Script/UnrealEd.MaterialGraphNode Name="{node_name}"',
                f'   Begin Object Class=/Script/Engine.MaterialExpressionWorldPosition Name="{expr_name}"',
                "   End Object",
                f'   Begin Object Name="{expr_name}"',
                f"      MaterialExpressionEditorX={pos_x}",
                f"      MaterialExpressionEditorY={pos_y}",
                f"      MaterialExpressionGuid={material_expression_guid}",
                "   End Object",
                f'   MaterialExpression=/Script/Engine.MaterialExpressionWorldPosition\'{expr_name}\'',
                f"   NodePosX={pos_x}",
                f"   NodePosY={pos_y}",
                "   AdvancedPinDisplay=Hidden",
                f"   NodeGuid={node_guid}",
                pin_line(
                    pin_id=stable_hex(seed, f"{node_name}:shader_offsets"),
                    pin_name="Shader Offsets",
                    pin_category="optional",
                    pin_subcategory="byte",
                    default_value="Absolute World Position (Including Material Shader Offsets)",
                    not_connectable=True,
                ),
                pin_line(
                    pin_id=output_pin_id,
                    pin_name="XYZ",
                    direction="EGPD_Output",
                    pin_category="mask",
                    linked_to=[(target_graph_name, target_pin_id)],
                ),
                "End Object",
            ]
        )

    if source_type == "camera_position_ws":
        return "\n".join(
            [
                f'Begin Object Class=/Script/UnrealEd.MaterialGraphNode Name="{node_name}"',
                f'   Begin Object Class=/Script/Engine.MaterialExpressionCameraPositionWS Name="{expr_name}"',
                "   End Object",
                f'   Begin Object Name="{expr_name}"',
                f"      MaterialExpressionEditorX={pos_x}",
                f"      MaterialExpressionEditorY={pos_y}",
                f"      MaterialExpressionGuid={material_expression_guid}",
                "   End Object",
                f'   MaterialExpression=/Script/Engine.MaterialExpressionCameraPositionWS\'{expr_name}\'',
                f"   NodePosX={pos_x}",
                f"   NodePosY={pos_y}",
                f"   NodeGuid={node_guid}",
                pin_line(
                    pin_id=output_pin_id,
                    pin_name="Output",
                    direction="EGPD_Output",
                    linked_to=[(target_graph_name, target_pin_id)],
                ),
                "End Object",
            ]
        )

    if source_type == "time":
        return "\n".join(
            [
                f'Begin Object Class=/Script/UnrealEd.MaterialGraphNode Name="{node_name}"',
                f'   Begin Object Class=/Script/Engine.MaterialExpressionTime Name="{expr_name}"',
                "   End Object",
                f'   Begin Object Name="{expr_name}"',
                f"      MaterialExpressionEditorX={pos_x}",
                f"      MaterialExpressionEditorY={pos_y}",
                f"      MaterialExpressionGuid={material_expression_guid}",
                "   End Object",
                f'   MaterialExpression=/Script/Engine.MaterialExpressionTime\'{expr_name}\'',
                f"   NodePosX={pos_x}",
                f"   NodePosY={pos_y}",
                f"   NodeGuid={node_guid}",
                pin_line(
                    pin_id=output_pin_id,
                    pin_name="Output",
                    direction="EGPD_Output",
                    linked_to=[(target_graph_name, target_pin_id)],
                ),
                "End Object",
            ]
        )

    if source_type == "scalar_parameter":
        param_name = spec["param_name"]
        default_value = spec["default_value"]
        return "\n".join(
            [
                f'Begin Object Class=/Script/UnrealEd.MaterialGraphNode Name="{node_name}"',
                f'   Begin Object Class=/Script/Engine.MaterialExpressionScalarParameter Name="{expr_name}"',
                "   End Object",
                f'   Begin Object Name="{expr_name}"',
                f"      DefaultValue={default_value}",
                f'      ParameterName="{param_name}"',
                f"      ExpressionGUID={stable_hex(seed, f'{node_name}:expression_guid')}",
                f"      MaterialExpressionEditorX={pos_x}",
                f"      MaterialExpressionEditorY={pos_y}",
                f"      MaterialExpressionGuid={material_expression_guid}",
                "   End Object",
                f'   MaterialExpression=/Script/Engine.MaterialExpressionScalarParameter\'{expr_name}\'',
                f"   NodePosX={pos_x}",
                f"   NodePosY={pos_y}",
                "   bCanRenameNode=True",
                f"   NodeGuid={node_guid}",
                pin_line(
                    pin_id=stable_hex(seed, f"{node_name}:default_value"),
                    pin_name="Default Value",
                    pin_category="optional",
                    pin_subcategory="red",
                    default_value=str(default_value),
                    not_connectable=True,
                ),
                pin_line(
                    pin_id=output_pin_id,
                    pin_name="Output",
                    direction="EGPD_Output",
                    linked_to=[(target_graph_name, target_pin_id)],
                ),
                "End Object",
            ]
        )

    if source_type == "constant3":
        default_value = spec["default_value"]
        return "\n".join(
            [
                f'Begin Object Class=/Script/UnrealEd.MaterialGraphNode Name="{node_name}"',
                f'   Begin Object Class=/Script/Engine.MaterialExpressionConstant3Vector Name="{expr_name}"',
                "   End Object",
                f'   Begin Object Name="{expr_name}"',
                f"      Constant=(R={default_value[0]},G={default_value[1]},B={default_value[2]},A=1.000000)",
                f"      MaterialExpressionEditorX={pos_x}",
                f"      MaterialExpressionEditorY={pos_y}",
                f"      MaterialExpressionGuid={material_expression_guid}",
                "   End Object",
                f'   MaterialExpression=/Script/Engine.MaterialExpressionConstant3Vector\'{expr_name}\'',
                f"   NodePosX={pos_x}",
                f"   NodePosY={pos_y}",
                f"   NodeGuid={node_guid}",
                pin_line(
                    pin_id=stable_hex(seed, f"{node_name}:constant"),
                    pin_name="Constant",
                    pin_category="optional",
                    pin_subcategory="rgb",
                    default_value=",".join(default_value),
                    not_connectable=True,
                ),
                pin_line(
                    pin_id=output_pin_id,
                    pin_name="Output",
                    direction="EGPD_Output",
                    pin_category="mask",
                    linked_to=[(target_graph_name, target_pin_id)],
                ),
                "End Object",
            ]
        )

    if source_type == "texture_coordinate":
        return "\n".join(
            [
                f'Begin Object Class=/Script/UnrealEd.MaterialGraphNode Name="{node_name}"',
                f'   Begin Object Class=/Script/Engine.MaterialExpressionTextureCoordinate Name="{expr_name}"',
                "   End Object",
                f'   Begin Object Name="{expr_name}"',
                f"      MaterialExpressionEditorX={pos_x}",
                f"      MaterialExpressionEditorY={pos_y}",
                f"      MaterialExpressionGuid={material_expression_guid}",
                "   End Object",
                f'   MaterialExpression=/Script/Engine.MaterialExpressionTextureCoordinate\'{expr_name}\'',
                f"   NodePosX={pos_x}",
                f"   NodePosY={pos_y}",
                f"   NodeGuid={node_guid}",
                pin_line(
                    pin_id=output_pin_id,
                    pin_name="Output",
                    direction="EGPD_Output",
                    linked_to=[(target_graph_name, target_pin_id)],
                ),
                "End Object",
            ]
        )

    if source_type == "texture_object_parameter":
        param_name = spec["param_name"]
        texture_path = spec.get("texture_path", '/Engine/EngineResources/DefaultTexture.DefaultTexture')
        sampler_type = spec.get("sampler_type", "SAMPLERTYPE_Color")
        return "\n".join(
            [
                f'Begin Object Class=/Script/UnrealEd.MaterialGraphNode Name="{node_name}"',
                f'   Begin Object Class=/Script/Engine.MaterialExpressionTextureObjectParameter Name="{expr_name}"',
                "   End Object",
                f'   Begin Object Name="{expr_name}"',
                f'      ParameterName="{param_name}"',
                f"      ExpressionGUID={stable_hex(seed, f'{node_name}:expression_guid')}",
                f'      Texture=Texture2D\'"{texture_path}"\'',
                f"      SamplerType={sampler_type}",
                f"      MaterialExpressionEditorX={pos_x}",
                f"      MaterialExpressionEditorY={pos_y}",
                f"      MaterialExpressionGuid={material_expression_guid}",
                "   End Object",
                f'   MaterialExpression=/Script/Engine.MaterialExpressionTextureObjectParameter\'{expr_name}\'',
                f"   NodePosX={pos_x}",
                f"   NodePosY={pos_y}",
                "   bCanRenameNode=True",
                f"   NodeGuid={node_guid}",
                pin_line(
                    pin_id=output_pin_id,
                    pin_name="Output",
                    direction="EGPD_Output",
                    linked_to=[(target_graph_name, target_pin_id)],
                ),
                "End Object",
            ]
        )

    raise ValueError(f"Unsupported source_type in first version: {source_type}")


def build_full_graph_export(args: argparse.Namespace) -> str:
    code = custom_export.read_code(Path(args.code_file))
    output_type = custom_export.normalize_output_type(args.output_type)
    inputs = custom_export.parse_inputs(args.input)
    additional_outputs = custom_export.parse_additional_outputs(args.additional_output)
    layout = read_layout(Path(args.layout_file))

    graph_node_name = layout.get("custom_node", {}).get("graph_node_name", "MaterialGraphNode_Custom_1")
    expression_name = layout.get("custom_node", {}).get("expression_name", "MaterialExpressionCustom_1")
    node_pos_x = layout.get("custom_node", {}).get("node_pos_x", 0)
    node_pos_y = layout.get("custom_node", {}).get("node_pos_y", 0)

    pin_map = {
        input_name: custom_export.stable_hex(args.seed, f"pin:input:{index}:{input_name}")
        for index, input_name in enumerate(inputs)
    }
    custom_input_links: dict[str, list[tuple[str, str]]] = {}

    node_blocks: list[str] = []
    for spec in layout.get("sources", []):
        input_name = spec["connect_to_input"]
        if input_name not in pin_map:
            raise ValueError(f"Layout references unknown input: {input_name}")
        custom_input_links.setdefault(input_name, []).append(
            (spec["graph_node_name"], source_output_pin_id(args.seed, spec["graph_node_name"]))
        )
        node_blocks.append(
            build_source_node(
                seed=args.seed,
                spec=spec,
                target_graph_name=graph_node_name,
                target_pin_id=pin_map[input_name],
            )
        )

    custom_block = custom_export.build_export_text(
        code=code,
        main_output_type=output_type,
        inputs=inputs,
        additional_outputs=additional_outputs,
        input_links=custom_input_links,
        output_links=None,
        defines=[],
        desc=args.desc,
        node_pos_x=node_pos_x,
        node_pos_y=node_pos_y,
        graph_node_name=graph_node_name,
        expression_name=expression_name,
        seed=args.seed,
        show_code=True,
    ).strip()

    node_blocks.append(custom_block)
    return "\n".join(node_blocks) + "\n"


def main() -> int:
    args = parse_args()
    export_text = build_full_graph_export(args)
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
