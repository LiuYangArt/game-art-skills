from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def check_balanced(code: str, open_ch: str, close_ch: str) -> bool:
    depth = 0
    for ch in code:
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Lightweight static checks for Unreal PCG HLSL node code.")
    ap.add_argument("--kernel-type", required=True, choices=["Custom", "PointGenerator", "PointProcessor", "AttributeProcessor", "AttributeSetProcessor"])
    ap.add_argument("--code-file", required=True)
    ap.add_argument("--paste-file")
    args = ap.parse_args()

    path = Path(args.code_file).resolve()
    code = path.read_text(encoding="utf-8-sig")
    errors = []
    warnings = []
    if "TODO" in code or "replace me" in code.lower():
        errors.append("Code contains TODO/placeholder text.")
    if re.search(r"\bMain\s*\(", code):
        warnings.append("Preset PCG Shader Source is normally a per-thread body and should not contain Main().")
    if not check_balanced(code, "{", "}"):
        errors.append("Unbalanced braces.")
    if not check_balanced(code, "(", ")"):
        errors.append("Unbalanced parentheses.")
    if re.search(r"\bwhile\s*\(", code):
        warnings.append("while loops are risky on GPU; prefer bounded for loops.")
    if re.search(r"\bdiscard\b|\bclip\s*\(", code):
        warnings.append("discard/clip is unusual for PCG compute-style kernels; verify engine support.")
    if args.kernel_type == "PointGenerator" and "ElementIndex" not in code:
        warnings.append("PointGenerator code usually maps ElementIndex to generated points.")
    if args.kernel_type in {"PointProcessor", "AttributeProcessor", "AttributeSetProcessor"} and "ElementIndex" not in code:
        warnings.append("Processor kernels usually consume an element index or equivalent input.")
    paste_result = validate_paste_export(Path(args.paste_file).resolve()) if args.paste_file else None
    if paste_result and not paste_result["ok"]:
        errors.extend(paste_result["errors"])
    result = {"ok": not errors, "errors": errors, "warnings": warnings, "code_file": str(path), "kernel_type": args.kernel_type}
    if paste_result:
        result["paste_file"] = paste_result["paste_file"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


def validate_paste_export(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    errors = []
    for token in [
        "Begin Object Class=/Script/PCGEditor.PCGEditorGraphNode",
        "PCGCustomHLSLSettings",
        'ShaderFunctions="',
        'ShaderSource="',
        "CustomProperties Pin",
    ]:
        if token not in text:
            errors.append(f"Paste export missing {token}")
    return {"ok": not errors, "errors": errors, "paste_file": str(path)}


if __name__ == "__main__":
    raise SystemExit(main())
