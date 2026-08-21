#!/usr/bin/env python3
"""Emit a UE 5.7 PCG Custom HLSL node that can be pasted into a PCG graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


KERNEL_TYPES = {
    "custom": "Custom",
    "pointgenerator": "PointGenerator",
    "pointprocessor": "PointProcessor",
    "attributeprocessor": "AttributeSetProcessor",
    "attributesetprocessor": "AttributeSetProcessor",
}

DATA_TYPES = {
    "point": ("/Script/PCG.PCGDataTypeInfoPoint", "Concrete Data", "Point Data"),
    "param": ("/Script/PCG.PCGDataTypeInfoParam", "Attribute Set", ""),
    "attribute": ("/Script/PCG.PCGDataTypeInfoParam", "Attribute Set", ""),
    "landscape": ("/Script/PCG.PCGDataTypeInfoLandscape", "Concrete Data", "Landscape Data"),
    "virtualtexture": ("/Script/PCG.PCGDataTypeInfoVirtualTexture", "Concrete Data", "Virtual Texture Data"),
    "texture2d": ("/Script/PCG.PCGDataTypeInfoBaseTexture2D", "Concrete Data", "Base Texture Data"),
}


@dataclass(frozen=True)
class Pin:
    label: str
    kind: str
    direction: str
    required: bool = False
    advanced: bool = False
    init_from: str | None = None


def stable_hex(seed: str) -> str:
    return hashlib.md5(seed.encode("utf-8")).hexdigest().upper()


def safe_name(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_")
    return result or "pcg_hlsl_node"


def normalize_kernel(value: str) -> str:
    key = re.sub(r"[^a-z]", "", value.lower())
    if key not in KERNEL_TYPES:
        raise ValueError(f"Unsupported kernel type: {value}")
    return KERNEL_TYPES[key]


def parse_pin(raw: str, direction: str) -> Pin:
    parts = [part.strip() for part in raw.split(":")]
    if len(parts) < 2 or len(parts) > 3:
        raise ValueError(f"Invalid pin {raw!r}; expected Name:Type[:InitFrom]")
    label, kind = parts[0], parts[1].lower()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", label):
        raise ValueError(f"Invalid pin name: {label!r}")
    if kind not in DATA_TYPES:
        raise ValueError(f"Unsupported pin type {kind!r}; use one of {sorted(DATA_TYPES)}")
    init_from = parts[2] if len(parts) == 3 and parts[2] else None
    return Pin(label=label, kind=kind, direction=direction, init_from=init_from)


def ue_escape(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\r\\n")


def allowed_types(kind: str) -> str:
    path = DATA_TYPES[kind][0]
    return f'(Ids=((Struct="/Script/CoreUObject.ScriptStruct\'{path}\'")))'


def settings_pin(pin: Pin) -> str:
    flags = [f'Label="{pin.label}"', f"AllowedTypes={allowed_types(pin.kind)}"]
    if pin.kind in {"landscape", "param", "attribute"}:
        flags.append("bAllowMultipleData=False")
    flags.append("bAllowMultipleConnections=False")
    if pin.required:
        flags.append("PinStatus=Required")
    return "(" + ",".join(flags) + ")"


def pin_properties(pin: Pin) -> str:
    flags = [f'Label="{pin.label}"', f"AllowedTypes={allowed_types(pin.kind)}"]
    if pin.kind in {"landscape", "param", "attribute"}:
        flags.append("bAllowMultipleData=False")
    if pin.direction == "input":
        flags.append("bAllowMultipleConnections=False")
    if pin.required:
        flags.append("PinStatus=Required")
    return "(" + ",".join(flags) + ")"


def custom_pin_export(pin: Pin, object_name: str, seed: str) -> str:
    _, category, subcategory = DATA_TYPES[pin.kind]
    direction = ',Direction="EGPD_Output"' if pin.direction == "output" else ""
    advanced = "True" if pin.advanced else "False"
    friendly = re.sub(r"(?<!^)(?=[A-Z])", " ", pin.label.replace("_", " ")).title()
    return (
        f'   CustomProperties Pin (PinId={stable_hex(seed + ":" + object_name)},PinName="{pin.label}",'
        f'PinFriendlyName="{friendly}"{direction},PinType.PinCategory="{category}",'
        f'PinType.PinSubCategory="{subcategory}",PinType.PinSubCategoryObject=None,'
        'PinType.PinSubCategoryMemberReference=(),PinType.PinValueType=(),PinType.ContainerType=None,'
        'PinType.bIsReference=False,PinType.bIsConst=False,PinType.bIsWeakPointer=False,'
        'PinType.bIsUObjectWrapper=False,PinType.bSerializeAsSinglePrecisionFloat=False,'
        'PersistentGuid=00000000000000000000000000000000,bHidden=False,bNotConnectable=False,'
        f'bDefaultValueIsReadOnly=False,bDefaultValueIsIgnored=False,bAdvancedView={advanced},bOrphanedPin=False,)'
    )


def advanced_custom_pin(label: str, object_name: str, seed: str) -> str:
    category = "" if label == "Execution Dependency" else "Attribute Set"
    return (
        f'   CustomProperties Pin (PinId={stable_hex(seed + ":" + object_name)},PinName="{label}",'
        f'PinFriendlyName="{label}",PinType.PinCategory="{category}",PinType.PinSubCategory="",'
        'PinType.PinSubCategoryObject=None,PinType.PinSubCategoryMemberReference=(),PinType.PinValueType=(),'
        'PinType.ContainerType=None,PinType.bIsReference=False,PinType.bIsConst=False,PinType.bIsWeakPointer=False,'
        'PinType.bIsUObjectWrapper=False,PinType.bSerializeAsSinglePrecisionFloat=False,'
        'PersistentGuid=00000000000000000000000000000000,bHidden=False,bNotConnectable=False,'
        'bDefaultValueIsReadOnly=False,bDefaultValueIsIgnored=False,bAdvancedView=True,bOrphanedPin=False,)'
    )


def build_node_export(spec: dict, functions: str, source: str) -> str:
    kernel = spec["kernel_type"]
    seed = f'{spec["name"]}:{kernel}:{spec["seed"]}'
    graph_node, node, settings = "PCGEditorGraphNode_0", "CustomHLSL_0", "PCGCustomHLSLSettings_0"
    inputs = [Pin(**item) for item in spec["input_pins"]]
    outputs = [Pin(**item) for item in spec["output_pins"]]
    data_pins = inputs + outputs
    pin_names = {id(pin): f"PCGPin_{index}" for index, pin in enumerate(data_pins)}
    advanced = ["Execution Dependency", "Overrides", "NumElements", "ThreadCountMultiplier", "FixedThreadCount", "Seed"]
    advanced_ids = {label: f"PCGPin_{len(data_pins) + index}" for index, label in enumerate(advanced)}

    lines = [
        f'Begin Object Class=/Script/PCGEditor.PCGEditorGraphNode Name="{graph_node}"',
        f'   Begin Object Class=/Script/PCG.PCGNode Name="{node}"',
    ]
    for pin in data_pins:
        lines += [f'      Begin Object Class=/Script/PCG.PCGPin Name="{pin_names[id(pin)]}"', "      End Object"]
    for label in advanced:
        lines += [f'      Begin Object Class=/Script/PCG.PCGPin Name="{advanced_ids[label]}"', "      End Object"]
    lines += [f'      Begin Object Class=/Script/PCG.PCGCustomHLSLSettings Name="{settings}"', "      End Object", "   End Object"]

    lines.append(f'   Begin Object Name="{node}"')
    for pin in data_pins:
        object_name = pin_names[id(pin)]
        lines += [
            f'      Begin Object Name="{object_name}"',
            f'         Node="/Script/PCG.PCGNode\'{graph_node}.{node}\'"',
            f"         Properties={pin_properties(pin)}",
            "      End Object",
        ]
    for label in advanced:
        object_name = advanced_ids[label]
        usage = ",Usage=DependencyOnly" if label == "Execution Dependency" else ""
        status = "Advanced" if label == "Execution Dependency" else "OverrideOrUserParam"
        lines += [
            f'      Begin Object Name="{object_name}"',
            f'         Node="/Script/PCG.PCGNode\'{graph_node}.{node}\'"',
            f'         Properties=(Label="{label}"{usage},PinStatus={status})',
            "      End Object",
        ]

    lines += [f'      Begin Object Name="{settings}"', f"         KernelType={kernel}"]
    if kernel == "PointGenerator" and not inputs:
        lines.append("         InputPins=")
    else:
        for index, pin in enumerate(inputs):
            lines.append(f"         InputPins({index})={settings_pin(pin)}")
    for index, pin in enumerate(outputs):
        init = f'(PinsToInititalizeFrom=("{pin.init_from}"))' if pin.init_from else "()"
        label = "" if pin.label == "Out" else f',Label="{pin.label}"'
        lines.append(f"         OutputPins({index})=(PropertiesGPU={init}{label},AllowedTypes={allowed_types(pin.kind)},bAllowMultipleData=False)")
    lines += [
        f'         ShaderFunctions="{ue_escape(functions)}"',
        f'         ShaderSource="{ue_escape(source)}"',
        f'         NumElements={spec["num_elements"]}',
        f'         Seed={spec["seed"]}',
        '         CachedOverridableParams(0)=(Label="NumElements",PropertiesNames=("NumElements"),PropertyClass="/Script/CoreUObject.Class\'/Script/PCG.PCGCustomHLSLSettings\'",bSupportsGPU=True,bRequiresGPUReadback=True,UnderlyingType=Integer32)',
        '         CachedOverridableParams(1)=(Label="ThreadCountMultiplier",PropertiesNames=("ThreadCountMultiplier"),PropertyClass="/Script/CoreUObject.Class\'/Script/PCG.PCGCustomHLSLSettings\'",bSupportsGPU=True,bRequiresGPUReadback=True,UnderlyingType=Integer32)',
        '         CachedOverridableParams(2)=(Label="FixedThreadCount",PropertiesNames=("FixedThreadCount"),PropertyClass="/Script/CoreUObject.Class\'/Script/PCG.PCGCustomHLSLSettings\'",bSupportsGPU=True,bRequiresGPUReadback=True,UnderlyingType=Integer32)',
        '         CachedOverridableParams(3)=(Label="Seed",PropertiesNames=("Seed"),PropertyClass="/Script/CoreUObject.Class\'/Script/PCG.PCGCustomHLSLSettings\'",UnderlyingType=Integer32)',
        "      End Object",
        "      PositionX=0",
        "      PositionY=0",
        f'      SettingsInterface="/Script/PCG.PCGCustomHLSLSettings\'{settings}\'"',
    ]
    for index, pin in enumerate(inputs):
        lines.append(f'      InputPins({index})="/Script/PCG.PCGPin\'{pin_names[id(pin)]}\'"')
    for index, label in enumerate(advanced, start=len(inputs)):
        lines.append(f'      InputPins({index})="/Script/PCG.PCGPin\'{advanced_ids[label]}\'"')
    for index, pin in enumerate(outputs):
        lines.append(f'      OutputPins({index})="/Script/PCG.PCGPin\'{pin_names[id(pin)]}\'"')
    lines += [
        "   End Object",
        f'   PCGNode="/Script/PCG.PCGNode\'{node}\'"',
        "   NodePosX=0",
        "   NodePosY=0",
        "   AdvancedPinDisplay=Hidden",
        "   bUserSetEnabledState=True",
        "   bCanRenameNode=True",
        f"   NodeGuid={stable_hex(seed + ':node')}",
    ]
    for pin in data_pins:
        lines.append(custom_pin_export(pin, pin_names[id(pin)], seed))
    for label in advanced:
        lines.append(advanced_custom_pin(label, advanced_ids[label], seed))
    lines.append("End Object")
    return "\n".join(lines) + "\n"


def validate_export(text: str, spec: dict, functions: str, source: str) -> None:
    required = [
        "Begin Object Class=/Script/PCGEditor.PCGEditorGraphNode",
        "Class=/Script/PCG.PCGCustomHLSLSettings",
        f'KernelType={spec["kernel_type"]}',
        'ShaderFunctions="',
        'ShaderSource="',
        "CustomProperties Pin",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise ValueError(f"Generated export is incomplete: {missing}")
    if functions and ue_escape(functions) not in text:
        raise ValueError("Shader Functions were not preserved")
    if source and ue_escape(source) not in text:
        raise ValueError("Shader Source was not preserved")
    for pin in spec["input_pins"] + spec["output_pins"]:
        if f'PinName="{pin["label"]}"' not in text:
            raise ValueError(f'Missing editor pin: {pin["label"]}')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit a paste-ready UE 5.7 PCG Custom HLSL node.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--kernel-type", required=True)
    parser.add_argument("--functions-file", required=True)
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--input-pin", action="append", default=[])
    parser.add_argument("--output-pin", action="append", default=[])
    parser.add_argument("--num-elements", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=1074217968)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    kernel = normalize_kernel(args.kernel_type)
    functions_path = Path(args.functions_file).resolve()
    source_path = Path(args.source_file).resolve()
    functions = functions_path.read_text(encoding="utf-8-sig")
    source = source_path.read_text(encoding="utf-8-sig")
    inputs = [parse_pin(value, "input") for value in args.input_pin]
    outputs = [parse_pin(value, "output") for value in args.output_pin]

    if kernel in {"PointProcessor", "AttributeSetProcessor"} and not any(pin.label == "In" for pin in inputs):
        inputs.insert(0, Pin("In", "point" if kernel == "PointProcessor" else "param", "input", required=True))
    if not outputs:
        kind = "param" if kernel == "AttributeSetProcessor" else "point"
        init_from = "In" if kernel in {"PointProcessor", "AttributeSetProcessor"} else None
        outputs = [Pin("Out", kind, "output", init_from=init_from)]

    base = safe_name(args.name)
    spec = {
        "name": base,
        "kernel_type": kernel,
        "num_elements": args.num_elements,
        "seed": args.seed,
        "functions_file": str(functions_path),
        "source_file": str(source_path),
        "input_pins": [asdict(pin) for pin in inputs],
        "output_pins": [asdict(pin) for pin in outputs],
    }
    export = build_node_export(spec, functions, source)
    validate_export(export, spec, functions, source)

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        out_dir / f"{base}_functions.md",
        out_dir / f"{base}_source.md",
        out_dir / f"{base}_pcg_node_paste.md",
        out_dir / f"{base}_pcg_node_spec.json",
    ]
    paths[0].write_text(functions.rstrip() + "\n", encoding="utf-8")
    paths[1].write_text(source.rstrip() + "\n", encoding="utf-8")
    paths[2].write_text(export, encoding="utf-8")
    paths[3].write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path in paths:
        print(str(path))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
