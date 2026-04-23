#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-path", required=True)
    parser.add_argument("p4_args", nargs=argparse.REMAINDER)
    return parser.parse_args()


def load_profile(config_path: str) -> dict:
    candidate = Path(config_path)
    if not candidate.exists():
        raise RuntimeError(
            f"Connection profile not found: {config_path}. "
            "Run scripts\\p4-init.ps1 or copy config\\p4-connection.template.json to config\\p4-connection.json first."
        )
    with candidate.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_profile_value(profile: dict, name: str, config_path: str, required: bool = False) -> str:
    value = profile.get(name, "")
    value = "" if value is None else str(value)
    if required and not value.strip():
        raise RuntimeError(f"Missing required field '{name}' in {config_path}")
    return value


def resolve_p4_command() -> str:
    executable = shutil.which("p4")
    if executable:
        return executable
    raise RuntimeError("p4 was not found on PATH.")


def build_command(executable: str, args: list[str]) -> list[str]:
    lowered = executable.lower()
    if lowered.endswith(".cmd") or lowered.endswith(".bat"):
        return ["cmd.exe", "/d", "/c", executable, *args]
    return [executable, *args]


def run_p4(executable: str, server: str, user: str, password: str, p4_args: list[str]) -> dict:
    arguments = ["-p", server, "-u", user]
    arguments.extend(p4_args or ["info"])

    env = os.environ.copy()
    if password.strip():
        env["P4PASSWD"] = password

    completed = subprocess.run(
        build_command(executable, arguments),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    return {
        "status": "ok",
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "exitCode": completed.returncode,
    }


def main() -> int:
    args = parse_args()
    p4_args = list(args.p4_args)
    if p4_args and p4_args[0] == "--":
        p4_args = p4_args[1:]

    try:
        profile = load_profile(args.config_path)
        server = get_profile_value(profile, "server", args.config_path, required=True)
        user = get_profile_value(profile, "user", args.config_path, required=True)
        password = get_profile_value(profile, "password", args.config_path)
        executable = resolve_p4_command()
        result = run_p4(executable, server, user, password, p4_args)
    except RuntimeError as exc:
        result = {
            "status": "error",
            "message": str(exc),
        }

    json.dump(result, sys.stdout, ensure_ascii=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
