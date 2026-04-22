#!/usr/bin/env python3
"""
Validate Houdini Wrangle VEX snippets by compiling and cooking a real node in hython.

Why this script uses hython instead of vcc as the primary validator:
Wrangle snippets rely on node-context syntax such as @P, @Cd, @ptnum, and
node-local chf()/chi()/chv()/chs()/chramp() calls. Those constructs are not a
plain standalone .vfl file, so the most trustworthy validation path is to load
real Houdini nodes and force a cook.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set


CHANNEL_PATTERNS = {
    "float": [r"\bchf\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", r"\bch\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"],
    "int": [r"\bchi\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"],
    "vector": [r"\bchv\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"],
    "string": [r"\bchs\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"],
    "ramp": [r"\bchramp\s*\(\s*['\"]([^'\"]+)['\"]\s*,"],
}

RUN_OVER_CHOICES = ("points", "primitives", "vertices", "detail")
NODE_TYPE_CHOICES = ("attribwrangle", "volumewrangle")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a Houdini Wrangle snippet by forcing a real hython cook."
    )
    parser.add_argument("--code-file", required=True, help="Path to a file containing the raw Wrangle snippet.")
    parser.add_argument(
        "--node-type",
        default="attribwrangle",
        choices=NODE_TYPE_CHOICES,
        help="Houdini node type to validate against. Default: attribwrangle",
    )
    parser.add_argument(
        "--run-over",
        default="points",
        choices=RUN_OVER_CHOICES,
        help="Run Over mode for attribwrangle. Ignored for volumewrangle. Default: points",
    )
    parser.add_argument(
        "--houdini-bin",
        help="Optional path to a Houdini bin directory or directly to hython.exe.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep the temporary .hip file on success for inspection.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a final machine-readable JSON payload in addition to the summary.",
    )
    return parser.parse_args()


def collect_channel_refs(code: str) -> Dict[str, List[str]]:
    refs = {kind: set() for kind in CHANNEL_PATTERNS}
    for kind, patterns in CHANNEL_PATTERNS.items():
        for pattern in patterns:
            refs[kind].update(match.strip() for match in re.findall(pattern, code) if match.strip())

    conflicts = {}
    for kind, names in refs.items():
        if kind == "ramp":
            continue
        for name in names:
            conflicts.setdefault(name, set()).add(kind)

    bad = {name: kinds for name, kinds in conflicts.items() if len(kinds) > 1}
    if bad:
        detail = ", ".join(f"{name}: {', '.join(sorted(kinds))}" for name, kinds in sorted(bad.items()))
        raise ValueError(f"Conflicting channel types detected: {detail}")

    return {kind: sorted(values) for kind, values in refs.items()}


def iter_hython_candidates(explicit: Optional[str]) -> Iterable[Path]:
    seen: Set[str] = set()

    def maybe_yield(candidate: Optional[Path]):
        if candidate is None:
            return
        text = str(candidate)
        if not text or text in seen:
            return
        seen.add(text)
        yield candidate

    if explicit:
        raw = Path(explicit)
        if raw.is_dir():
            yield from maybe_yield(raw / "hython.exe")
        else:
            yield from maybe_yield(raw)

    for name in ("hython", "hython.exe"):
        found = shutil.which(name)
        if found:
            yield from maybe_yield(Path(found))

    hfs = os.environ.get("HFS")
    if hfs:
        yield from maybe_yield(Path(hfs) / "bin" / "hython.exe")

    common_root = Path(r"C:\Program Files\Side Effects Software")
    if common_root.exists():
        for child in sorted(common_root.glob("Houdini*"), reverse=True):
            yield from maybe_yield(child / "bin" / "hython.exe")


def find_hython(explicit: Optional[str]) -> Optional[Path]:
    for candidate in iter_hython_candidates(explicit):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


BOOTSTRAP = r'''
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

import hou


def fail(message, *, temp_hip=None, errors=None, warnings=None):
    payload = {
        "ok": False,
        "message": message,
        "temp_hip": temp_hip,
        "errors": errors or [],
        "warnings": warnings or [],
    }
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(1)


def succeed(message, *, temp_hip=None, errors=None, warnings=None, created_parms=None):
    payload = {
        "ok": True,
        "message": message,
        "temp_hip": temp_hip,
        "errors": errors or [],
        "warnings": warnings or [],
        "created_parms": created_parms or [],
    }
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)


def ensure_parm(node, name, kind):
    if node.parm(name) is not None:
        return False

    group = node.parmTemplateGroup()
    if kind == "float":
        template = hou.FloatParmTemplate(name, name, 1, default_value=(0.0,))
    elif kind == "int":
        template = hou.IntParmTemplate(name, name, 1, default_value=(0,))
    elif kind == "vector":
        template = hou.FloatParmTemplate(
            name,
            name,
            3,
            default_value=(0.0, 0.0, 0.0),
            naming_scheme=hou.parmNamingScheme.XYZW,
        )
    elif kind == "string":
        template = hou.StringParmTemplate(name, name, 1, default_value=("",))
    elif kind == "ramp":
        template = hou.RampParmTemplate(name, name, hou.rampParmType.Float)
    else:
        raise ValueError(f"Unsupported parm kind: {kind}")

    group.append(template)
    node.setParmTemplateGroup(group)
    return True


def configure_run_over(node, desired):
    parm = node.parm("class")
    if parm is None:
        return

    normalized = desired.lower().replace(" ", "")
    items = list(parm.menuItems())
    labels = list(parm.menuLabels())

    for token in items:
        if token.lower().replace(" ", "") == normalized:
            parm.set(token)
            return

    for index, label in enumerate(labels):
        if label.lower().replace(" ", "") == normalized:
            if index < len(items):
                parm.set(items[index])
            else:
                parm.set(index)
            return

    fallback = {
        "points": 0,
        "primitives": 1,
        "vertices": 2,
        "detail": 3,
    }
    if desired in fallback:
        parm.set(fallback[desired])


spec = json.loads(os.environ["CODEX_VEX_VALIDATE_SPEC"])
code = Path(spec["code_file"]).read_text(encoding="utf-8")
channel_refs = spec["channel_refs"]
keep_temp = spec["keep_temp"]
node_type = spec["node_type"]
run_over = spec["run_over"]

temp_dir = Path(tempfile.mkdtemp(prefix="codex_houdini_vex_"))
temp_hip = temp_dir / "validate_vex.hip"
created_parms = []

try:
    obj = hou.node("/obj")
    if obj is None:
        fail("Failed to locate /obj in Houdini session.")

    geo = obj.createNode("geo", node_name="codex_vex_validate")
    for child in list(geo.children()):
        child.destroy()

    if node_type == "attribwrangle":
        source = geo.createNode("box", "input_geo")
        normal = geo.createNode("normal", "normals")
        normal.setInput(0, source)
        target = geo.createNode("attribwrangle", "validate_vex")
        target.setInput(0, normal)
        configure_run_over(target, run_over)
    elif node_type == "volumewrangle":
        source = geo.createNode("volume", "input_volume")
        name_parm = source.parm("name")
        if name_parm is not None:
            name_parm.set("density")
        target = geo.createNode("volumewrangle", "validate_vex")
        target.setInput(0, source)
    else:
        fail(f"Unsupported node_type: {node_type}", temp_hip=str(temp_hip))

    snippet_parm = None
    for parm_name in ("snippet", "code", "vexsnippet"):
        snippet_parm = target.parm(parm_name)
        if snippet_parm is not None:
            break
    if snippet_parm is None:
        fail("Could not find snippet parameter on target node.", temp_hip=str(temp_hip))

    for kind, names in channel_refs.items():
        for name in names:
            if ensure_parm(target, name, kind):
                created_parms.append(f"{kind}:{name}")

    snippet_parm.set(code)
    target.moveToGoodPosition()
    geo.layoutChildren()
    target.cook(force=True)

    errors = list(target.errors())
    warnings = list(target.warnings())
    hou.hipFile.save(str(temp_hip))

    if errors:
        fail("Node cook failed with Houdini errors.", temp_hip=str(temp_hip), errors=errors, warnings=warnings)

    if not keep_temp:
        try:
            temp_hip.unlink(missing_ok=True)
            temp_dir.rmdir()
            temp_hip_text = None
        except Exception:
            temp_hip_text = str(temp_hip)
    else:
        temp_hip_text = str(temp_hip)

    succeed(
        "Houdini node compiled and cooked successfully.",
        temp_hip=temp_hip_text,
        warnings=warnings,
        created_parms=created_parms,
    )
except Exception as exc:
    tb = traceback.format_exc()
    try:
        hou.hipFile.save(str(temp_hip))
        temp_hip_text = str(temp_hip)
    except Exception:
        temp_hip_text = None
    fail(f"Unhandled validation error: {exc}", temp_hip=temp_hip_text, errors=[tb])
'''


def run_validation(
    hython_path: Path,
    code_file: Path,
    node_type: str,
    run_over: str,
    keep_temp: bool,
    channel_refs: Dict[str, List[str]],
) -> subprocess.CompletedProcess[str]:
    spec = {
        "code_file": str(code_file.resolve()),
        "node_type": node_type,
        "run_over": run_over,
        "keep_temp": keep_temp,
        "channel_refs": channel_refs,
    }
    env = os.environ.copy()
    env["CODEX_VEX_VALIDATE_SPEC"] = json.dumps(spec, ensure_ascii=False)
    return subprocess.run(
        [str(hython_path), "-c", BOOTSTRAP],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def parse_payload(stdout: str) -> Dict[str, object]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return {"ok": False, "message": "Validator produced no output.", "errors": [], "warnings": []}

    last = lines[-1]
    try:
        payload = json.loads(last)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    return {"ok": False, "message": "Validator returned non-JSON output.", "errors": lines, "warnings": []}


def print_summary(payload: Dict[str, object], *, hython_path: Optional[Path]) -> None:
    status = "PASS" if payload.get("ok") else "FAIL"
    print(f"[{status}] {payload.get('message', 'No message')}")
    if hython_path is not None:
        print(f"hython: {hython_path}")

    temp_hip = payload.get("temp_hip")
    if temp_hip:
        print(f"temp_hip: {temp_hip}")

    created = payload.get("created_parms") or []
    if created:
        print("created_parms:")
        for item in created:
            print(f"  - {item}")

    warnings = payload.get("warnings") or []
    if warnings:
        print("warnings:")
        for item in warnings:
            print(f"  - {item}")

    errors = payload.get("errors") or []
    if errors:
        print("errors:")
        for item in errors:
            print(f"  - {item}")


def main() -> int:
    args = parse_args()
    code_file = Path(args.code_file)
    if not code_file.exists():
        print(f"[FAIL] Code file not found: {code_file}")
        return 1

    code = code_file.read_text(encoding="utf-8")
    try:
        channel_refs = collect_channel_refs(code)
    except ValueError as exc:
        print(f"[FAIL] {exc}")
        return 1

    hython_path = find_hython(args.houdini_bin)
    if hython_path is None:
        print("[FAIL] Could not find hython. Install Houdini or pass --houdini-bin.")
        return 1

    result = run_validation(
        hython_path=hython_path,
        code_file=code_file,
        node_type=args.node_type,
        run_over=args.run_over,
        keep_temp=args.keep_temp,
        channel_refs=channel_refs,
    )

    payload = parse_payload(result.stdout)
    if result.stderr.strip():
        payload.setdefault("errors", [])
        payload["errors"] = list(payload.get("errors") or []) + [result.stderr.strip()]

    print_summary(payload, hython_path=hython_path)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))

    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())