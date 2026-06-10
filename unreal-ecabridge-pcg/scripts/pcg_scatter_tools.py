#!/usr/bin/env python3
"""Repeatable ECABridge helpers for Paralogue PCG scatter graphs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from eca_call import call_tool, result_payload  # noqa: E402

DEFAULT_MESH = "/Script/Engine.StaticMesh'/Game/FDBattleEnvContent/Meshes/BasicPrimitives/SM_Cube_100.SM_Cube_100'"

DEFAULT_PARAM_EDGES = {
    "Meshes": {"to_node": "MatchAndSetAttributes_0", "to_pin": "Match Data"},
    "VoxelSize": {"to_node": "VolumeSampler_0", "to_pin": "VoxelSize"},
    "OffsetRange": {"to_node": "TransformPoints_0", "to_pin": "OffsetMax"},
    "OffsetRange@NegateInput": {"to_node": "AttributeMathsOp_0", "to_pin": "InputSource1"},
    "RotationRange": {"to_node": "TransformPoints_0", "to_pin": "RotationMax"},
    "RotationRange@NegateInput": {"to_node": "AttributeMathsOp_1", "to_pin": "InputSource1"},
    "ScaleMin": {"to_node": "TransformPoints_0", "to_pin": "ScaleMin"},
    "ScaleMax": {"to_node": "TransformPoints_0", "to_pin": "ScaleMax"},
    "UniformScale": {"to_node": "TransformPoints_0", "to_pin": "bUniformScale"},
}

DEFAULT_REQUIRED_EDGES = [
    {
        "from_node": "AttributeMathsOp_0",
        "from_pin": "Out",
        "to_node": "TransformPoints_0",
        "to_pin": "OffsetMin",
    },
    {
        "from_node": "AttributeMathsOp_1",
        "from_pin": "Out",
        "to_node": "TransformPoints_0",
        "to_pin": "RotationMin",
    },
]

DEFAULT_VALUES = {
    "Meshes": [DEFAULT_MESH],
    "VoxelSize": [180.0, 180.0, 180.0],
    "OffsetRange": [0.0, 0.0, 0.0],
    "RotationRange": [0.0, 0.0, 0.0],
    "ScaleMin": [1.0, 1.0, 1.0],
    "ScaleMax": [1.0, 1.0, 1.0],
    "UniformScale": True,
}


def param_name(mapping_key: str) -> str:
    return mapping_key.split("@", 1)[0]


def ec(tool: str, args: dict[str, Any] | None = None) -> Any:
    return result_payload(call_tool(tool, args or {}))


def execute_script(script: str) -> Any:
    payload = ec("execute_script", {"script": script})
    logs = payload.get("log_output") or [] if isinstance(payload, dict) else []
    if logs:
        errors = [entry.get("output", "") for entry in logs if entry.get("type") == "error"]
        if errors:
            raise RuntimeError("execute_script errors:\n" + "".join(errors))
    result = payload.get("command_result") if isinstance(payload, dict) else None
    if result == "None":
        return None
    return result


def dump_graph(graph_path: str) -> dict[str, Any]:
    return ec("dump_pcg_graph", {"graph_path": graph_path})


def save_asset(graph_path: str) -> Any:
    script = f"""
import unreal

def run():
    path = {graph_path!r}
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if not asset:
        raise RuntimeError('Failed to load ' + path)
    return {{'saved': unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)}}
"""
    return execute_script(script)


def generic_getters(graph_path: str) -> dict[str, list[dict[str, str]]]:
    script = f"""
import unreal

def _get(obj, name):
    try:
        return str(obj.get_editor_property(name))
    except Exception:
        return ''

def run():
    graph = unreal.EditorAssetLibrary.load_asset({graph_path!r})
    if not graph:
        raise RuntimeError('Failed to load graph')
    rows = []
    for node in graph.get_editor_property('nodes'):
        settings = node.get_settings()
        if 'GenericUserParameterGet' in settings.get_class().get_name():
            rows.append({{
                'node': node.get_name(),
                'path': _get(settings, 'PropertyPath'),
                'out': _get(settings, 'OutputAttributeName'),
            }})
    return rows
"""
    rows = execute_script(script) or []
    by_path: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_path.setdefault(row.get("path", ""), []).append(row)
    return by_path


def edge_exists(graph: dict[str, Any], from_node: str, to_node: str, to_pin: str, from_pin: str = "Out") -> bool:
    for edge in graph.get("edges", []):
        if (
            edge.get("from_node_id") == from_node
            and edge.get("from_pin") == from_pin
            and edge.get("to_node_id") == to_node
            and edge.get("to_pin") == to_pin
        ):
            return True
    return False


def pin_sources(graph: dict[str, Any], to_node: str, to_pin: str) -> list[dict[str, Any]]:
    return [edge for edge in graph.get("edges", []) if edge.get("to_node_id") == to_node and edge.get("to_pin") == to_pin]


def wire_params(graph_path: str, mapping: dict[str, dict[str, str]], *, allow_multiple: bool = False) -> dict[str, Any]:
    graph = dump_graph(graph_path)
    getters = generic_getters(graph_path)
    params = {p["name"] for p in graph.get("parameters", [])}
    created: list[str] = []
    connected: list[str] = []
    rewired: list[str] = []
    warnings: list[str] = []

    for index, (mapping_key, target) in enumerate(mapping.items()):
        param = param_name(mapping_key)
        if param not in params:
            warnings.append(f"Missing graph parameter: {param}")
            continue

        graph = dump_graph(graph_path)
        getters = generic_getters(graph_path)
        getter_by_node = {row["node"]: row for rows in getters.values() for row in rows}
        existing = pin_sources(graph, target["to_node"], target["to_pin"])
        rows = getters.get(param) or []

        # If the target pin is already driven by a generic getter, that node is the
        # safest one to reuse. This repairs graphs where the edge is right but the
        # getter PropertyPath was accidentally changed.
        if existing and existing[0].get("from_node_id") in getter_by_node:
            node_id = existing[0]["from_node_id"]
            if getter_by_node[node_id].get("path") != param:
                rewired.append(f"{node_id}:{getter_by_node[node_id].get('path')}->{param}")
        elif rows:
            node_id = rows[0]["node"]
            if len(rows) > 1:
                warnings.append(f"Multiple getter nodes for {param}; using {node_id}")
        else:
            node = ec(
                "add_pcg_node",
                {
                    "graph_path": graph_path,
                    "settings_class": "PCGGenericUserParameterGetSettings",
                    "position_x": -450,
                    "position_y": 360 + index * 100,
                },
            )
            node_id = node["node_id"]
            created.append(node_id)

        for prop in ("PropertyPath", "OutputAttributeName"):
            ec(
                "set_pcg_node_property",
                {"graph_path": graph_path, "node_id": node_id, "property_name": prop, "value": param},
            )

        graph = dump_graph(graph_path)
        if edge_exists(graph, node_id, target["to_node"], target["to_pin"]):
            continue
        existing = pin_sources(graph, target["to_node"], target["to_pin"])
        if existing and not allow_multiple:
            warnings.append(f"Pin already connected, skipped: {target['to_node']}.{target['to_pin']}")
            continue
        ec(
            "connect_pcg_nodes",
            {
                "graph_path": graph_path,
                "from_node_id": node_id,
                "from_pin": "Out",
                "to_node_id": target["to_node"],
                "to_pin": target["to_pin"],
            },
        )
        connected.append(f"{mapping_key}->{target['to_node']}.{target['to_pin']}")

    saved = save_asset(graph_path)
    final_graph = dump_graph(graph_path)
    return {
        "graph_path": graph_path,
        "created_getters": created,
        "connected": connected,
        "repaired_getters": rewired,
        "warnings": warnings,
        "saved": saved,
        "edge_count": final_graph.get("edge_count"),
    }


def ue_vector(value: list[float]) -> str:
    if len(value) != 3:
        raise ValueError(f"Vector defaults require 3 numbers: {value}")
    return f"(X={float(value[0]):.6f},Y={float(value[1]):.6f},Z={float(value[2]):.6f})"


def set_defaults(graph_path: str, values: dict[str, Any]) -> dict[str, Any]:
    script = f"""
import json
import re
import unreal

VALUES = json.loads({json.dumps(json.dumps(values))!r})
GRAPH_PATH = {graph_path!r}


def _vector(value):
    if len(value) != 3:
        raise RuntimeError('Vector default must have 3 values')
    return '(X={{:.6f}},Y={{:.6f}},Z={{:.6f}})'.format(float(value[0]), float(value[1]), float(value[2]))


def _mesh_array(meshes):
    return '(' + ','.join('"' + str(mesh).replace('"', '\\"') + '"' for mesh in meshes) + ')'


def _replace_field(text, name, replacement):
    pattern = r'(' + re.escape(name) + r'=)(\\([^)]*\\)|True|False)'
    new_text, count = re.subn(pattern, r'\\1' + replacement, text, count=1)
    if count != 1:
        raise RuntimeError('Failed to replace parameter default: ' + name)
    return new_text


def run():
    graph = unreal.EditorAssetLibrary.load_asset(GRAPH_PATH)
    if not graph:
        raise RuntimeError('Failed to load ' + GRAPH_PATH)
    bag = graph.get_editor_property('user_parameters')
    before = bag.export_text()
    after = before
    for name, value in VALUES.items():
        if name == 'Meshes':
            after = _replace_field(after, name, _mesh_array(value))
        elif isinstance(value, bool):
            after = _replace_field(after, name, 'True' if value else 'False')
        elif isinstance(value, list):
            after = _replace_field(after, name, _vector(value))
        else:
            raise RuntimeError('Unsupported default type for ' + name)
    if after != before:
        bag.import_text(after)
        graph.set_editor_property('user_parameters', bag)
        graph.modify()
    saved = unreal.EditorAssetLibrary.save_asset(GRAPH_PATH, only_if_is_dirty=False)
    check = graph.get_editor_property('user_parameters').export_text()
    return {{'saved': saved, 'before': before, 'after': check}}
"""
    return execute_script(script)


def validate_graph(graph_path: str, mapping: dict[str, dict[str, str]]) -> dict[str, Any]:
    graph = dump_graph(graph_path)
    params = {p["name"] for p in graph.get("parameters", [])}
    missing_params = sorted({param_name(name) for name in mapping if param_name(name) not in params})

    getters = generic_getters(graph_path)
    getter_by_node = {row["node"]: row for rows in getters.values() for row in rows}

    missing_edges = []
    wrong_getters = []
    for mapping_key, target in mapping.items():
        param = param_name(mapping_key)
        sources = pin_sources(graph, target["to_node"], target["to_pin"])
        if not sources:
            missing_edges.append(f"{mapping_key}->{target['to_node']}.{target['to_pin']}")
            continue
        source_node = sources[0].get("from_node_id")
        getter = getter_by_node.get(source_node)
        if not getter:
            wrong_getters.append(f"{param}: source {source_node} is not a GenericGraphParameter getter")
            continue
        if getter.get("path") != param or getter.get("out") != param:
            wrong_getters.append(
                f"{mapping_key}: {source_node} path={getter.get('path')} out={getter.get('out')}"
            )

    for edge in DEFAULT_REQUIRED_EDGES:
        if not edge_exists(graph, edge["from_node"], edge["to_node"], edge["to_pin"], edge["from_pin"]):
            missing_edges.append(
                f"{edge['from_node']}.{edge['from_pin']}->{edge['to_node']}.{edge['to_pin']}"
            )

    validation = ec("validate_asset", {"asset_path": graph_path})
    ok = not missing_params and not missing_edges and not wrong_getters and validation.get("is_valid") is True
    return {
        "ok": ok,
        "graph_path": graph_path,
        "missing_params": missing_params,
        "missing_edges": missing_edges,
        "wrong_getters": wrong_getters,
        "asset_validation": validation,
        "node_count": graph.get("node_count"),
        "edge_count": graph.get("edge_count"),
    }


def parse_json_arg(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    if raw.startswith("@"):
        return json.loads(Path(raw[1:]).read_text(encoding="utf-8"))
    return json.loads(raw)


def command_wire(args: argparse.Namespace) -> dict[str, Any]:
    mapping = parse_json_arg(args.mapping_json, DEFAULT_PARAM_EDGES)
    return wire_params(args.graph, mapping, allow_multiple=args.allow_multiple)


def command_defaults(args: argparse.Namespace) -> dict[str, Any]:
    values = dict(DEFAULT_VALUES)
    values.update(parse_json_arg(args.values_json, {}))
    return set_defaults(args.graph, values)


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    mapping = parse_json_arg(args.mapping_json, DEFAULT_PARAM_EDGES)
    return validate_graph(args.graph, mapping)


def command_repair_scatter(args: argparse.Namespace) -> dict[str, Any]:
    mapping = parse_json_arg(args.mapping_json, DEFAULT_PARAM_EDGES)
    values = dict(DEFAULT_VALUES)
    values.update(parse_json_arg(args.values_json, {}))
    wired = wire_params(args.graph, mapping, allow_multiple=args.allow_multiple)
    defaults = set_defaults(args.graph, values)
    validation = validate_graph(args.graph, mapping)
    return {"wired": wired, "defaults": defaults, "validation": validation}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PCG scatter graph helpers for ECABridge.")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--graph", required=True, help="Target PCG graph asset path, e.g. /Game/Folder/PCG_MyScatter")

    wire = sub.add_parser("wire-params", help="Create/reuse graph parameter getter nodes and wire override pins.")
    common(wire)
    wire.add_argument("--mapping-json", default=None, help="JSON object or @file. Defaults to cube scatter mapping.")
    wire.add_argument("--allow-multiple", action="store_true")
    wire.set_defaults(func=command_wire)

    defaults = sub.add_parser("set-defaults", help="Patch graph parameter defaults through InstancedPropertyBag text.")
    common(defaults)
    defaults.add_argument("--values-json", default=None, help="JSON object or @file overriding default values.")
    defaults.set_defaults(func=command_defaults)

    validate = sub.add_parser("validate", help="Check required params, getter wiring, and validate_asset.")
    common(validate)
    validate.add_argument("--mapping-json", default=None)
    validate.set_defaults(func=command_validate)

    repair = sub.add_parser("repair-scatter", help="Wire params, set defaults, save, and validate.")
    common(repair)
    repair.add_argument("--mapping-json", default=None)
    repair.add_argument("--values-json", default=None)
    repair.add_argument("--allow-multiple", action="store_true")
    repair.set_defaults(func=command_repair_scatter)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.func(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok", True) is not False else 2
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())