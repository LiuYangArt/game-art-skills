from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def unescape_ue_string(s: str) -> str:
    return bytes(s, "utf-8").decode("unicode_escape").replace(chr(13), "")


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract PCG HLSL code/spec hints from copied Unreal node export text.")
    ap.add_argument("--export-file", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--name", default="extracted_pcg_hlsl")
    args = ap.parse_args()

    export_path = Path(args.export_file).resolve()
    text = export_path.read_text(encoding="utf-8-sig")
    kernel = re.search(r"\bKernelType=([A-Za-z0-9_]+)", text)
    functions = re.search(r'ShaderFunctions="((?:\\.|[^"\\])*)"', text, re.S)
    source = re.search(r'ShaderSource="((?:\\.|[^"\\])*)"', text, re.S)
    labels = re.findall(r'Properties=\(Label="([^"]+)"', text)
    spec = {
        "source_export_file": str(export_path),
        "kernel_type": kernel.group(1) if kernel else None,
        "pin_labels": sorted(set(labels), key=labels.index),
        "cached_overridable_params": re.findall(r'CachedOverridableParams\(\d+\)=\(Label="([^"]+)"', text),
    }
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", args.name).strip("_") or "extracted_pcg_hlsl"
    spec_path = out_dir / f"{base}_pcg_node_spec.json"
    functions_path = out_dir / f"{base}_functions.md"
    source_path = out_dir / f"{base}_source.md"
    functions_code = unescape_ue_string(functions.group(1)) if functions else ""
    source_code = unescape_ue_string(source.group(1)) if source else ""
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    functions_path.write_text(functions_code, encoding="utf-8", newline="\n")
    source_path.write_text(source_code, encoding="utf-8", newline="\n")
    print(json.dumps({"functions": str(functions_path), "source": str(source_path), "spec": str(spec_path), "has_shader_functions": bool(functions), "has_shader_source": bool(source)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
