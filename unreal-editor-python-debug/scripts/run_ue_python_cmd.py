#!/usr/bin/env python3
"""
Run UnrealEditor-Cmd with PythonScriptCommandlet.

Default behavior:
- discover installed UE_* folders under C:\\Program Files\\Epic Games
- choose the lowest installed version
- run a Python probe script against a .uproject
- print the latest log path and optional filtered lines
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run UnrealEditor-Cmd.exe with a Python probe script.")
    parser.add_argument("--project", required=True, help="Path to the .uproject file.")
    parser.add_argument("--script", required=True, help="Path to the Unreal Python script to execute.")
    parser.add_argument("--engine-root", help="Explicit Unreal Engine root, e.g. C:\\Program Files\\Epic Games\\UE_5.5")
    parser.add_argument("--engine-version", help="Installed engine version like 5.5 or 5.7")
    parser.add_argument("--tail", type=int, default=80, help="Tail N lines from the newest log. Default: 80")
    parser.add_argument("--grep", action="append", default=[], help="Only print log lines containing this string. Repeatable.")
    parser.add_argument("--env", action="append", default=[], help="Extra environment variables in KEY=VALUE form. Repeatable.")
    parser.add_argument("--nullrhi", action="store_true", help="Add -NullRHI for headless probes that do not need rendering.")
    parser.add_argument("--stdout", action="store_true", help="Pass -stdout -FullStdOutLogOutput to UnrealEditor-Cmd.")
    parser.add_argument(
        "--quiet-editor-output",
        action="store_true",
        help="Capture UnrealEditor-Cmd stdout/stderr and only print it when the process exits non-zero.",
    )
    parser.add_argument("--extra-arg", action="append", default=[], help="Extra raw Unreal command-line argument. Repeatable.")
    return parser.parse_args()


def parse_version_tuple(name: str) -> tuple[int, ...] | None:
    match = re.fullmatch(r"UE_(\d+)(?:\.(\d+))?(?:\.(\d+))?", name)
    if not match:
        return None
    parts = [int(part) for part in match.groups() if part is not None]
    return tuple(parts)


def discover_engine_root(explicit_version: str | None) -> Path:
    base = Path(r"C:\Program Files\Epic Games")
    if not base.exists():
        raise FileNotFoundError(f"Engine base directory not found: {base}")

    candidates: list[tuple[tuple[int, ...], Path]] = []
    for child in base.iterdir():
        if not child.is_dir():
            continue
        version = parse_version_tuple(child.name)
        if version is None:
            continue
        if explicit_version and child.name != f"UE_{explicit_version}":
            continue
        candidates.append((version, child))

    if not candidates:
        if explicit_version:
            raise FileNotFoundError(f"Could not find installed Unreal version UE_{explicit_version}")
        raise FileNotFoundError("Could not find any installed Unreal Engine folders matching UE_*")

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def build_editor_cmd(engine_root: Path) -> Path:
    path = engine_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"
    if not path.exists():
        raise FileNotFoundError(f"UnrealEditor-Cmd.exe not found: {path}")
    return path


def parse_env_pairs(items: list[str]) -> dict[str, str]:
    env_map: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --env value: {item}. Expected KEY=VALUE")
        key, value = item.split("=", 1)
        env_map[key] = value
    return env_map


def newest_log(log_dir: Path) -> Path | None:
    if not log_dir.exists():
        return None
    logs = sorted(log_dir.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def info(message: str) -> None:
    print(f"[INFO] {message}", flush=True)


def error(message: str) -> None:
    print(f"[ERROR] {message}", flush=True)


def print_log_excerpt(log_path: Path, tail: int, grep: list[str]) -> None:
    if not log_path.exists():
        info(f"Log file does not exist: {log_path}")
        return

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if grep:
        matched = [line for line in lines if any(token in line for token in grep)]
        info("Matching log lines:")
        for line in matched[-tail:]:
            print(line)
        if not matched:
            info("No log lines matched the provided grep tokens.")
        return

    info(f"Last {min(tail, len(lines))} lines from log:")
    for line in lines[-tail:]:
        print(line)


def main() -> int:
    args = parse_args()
    if args.stdout and args.quiet_editor_output:
        raise ValueError("--stdout and --quiet-editor-output cannot be used together")

    project = Path(args.project)
    script = Path(args.script)
    if not project.exists():
        raise FileNotFoundError(f".uproject not found: {project}")
    if not script.exists():
        raise FileNotFoundError(f"Python script not found: {script}")

    engine_root = Path(args.engine_root) if args.engine_root else discover_engine_root(args.engine_version)
    editor_cmd = build_editor_cmd(engine_root)

    project_root = project.parent
    log_dir = project_root / "Saved" / "Logs"
    before_log = newest_log(log_dir)

    env = os.environ.copy()
    env.update(parse_env_pairs(args.env))

    normalized_script = script.as_posix()
    command = [
        str(editor_cmd),
        str(project),
        "-run=pythonscript",
        f"-script={normalized_script}",
        "-unattended",
        "-nop4",
        "-nosplash",
    ]

    if args.nullrhi:
        command.append("-NullRHI")
    if args.stdout:
        command.extend(["-stdout", "-FullStdOutLogOutput"])
    command.extend(args.extra_arg)

    info(f"Engine root: {engine_root}")
    info(f"Editor cmd: {editor_cmd}")
    info(f"Project: {project}")
    info(f"Script: {normalized_script}")
    info("Command:")
    print(" ".join(f'"{part}"' if " " in part else part for part in command), flush=True)

    process = subprocess.run(
        command,
        env=env,
        text=True,
        capture_output=args.quiet_editor_output,
    )

    if args.quiet_editor_output and process.returncode != 0:
        if process.stdout:
            error("UnrealEditor-Cmd stdout:")
            print(process.stdout, end="" if process.stdout.endswith("\n") else "\n", flush=True)
        if process.stderr:
            error("UnrealEditor-Cmd stderr:")
            print(process.stderr, end="" if process.stderr.endswith("\n") else "\n", flush=True)

    after_log = newest_log(log_dir)

    if after_log:
        info(f"Latest log: {after_log}")
        if before_log is None or after_log != before_log or args.grep or args.tail:
            print_log_excerpt(after_log, args.tail, args.grep)
    else:
        info(f"No log file found under: {log_dir}")

    return process.returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        error(str(exc))
        sys.exit(2)
