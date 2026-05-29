#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
from pathlib import Path


def load_profile(config_path: str) -> dict:
    candidate = Path(config_path)
    if not candidate.exists():
        raise RuntimeError(
            f"Connection profile not found: {config_path}. "
            "Run scripts\\p4-init.ps1 or copy config\\p4-connection.template.json to config\\p4-connection.json first."
        )
    with candidate.open('r', encoding='utf-8') as handle:
        return json.load(handle)


def get_profile_value(profile: dict, name: str, config_path: str, required: bool = False) -> str:
    value = profile.get(name, '')
    value = '' if value is None else str(value)
    if required and not value.strip():
        raise RuntimeError(f"Missing required field '{name}' in {config_path}")
    return value


def resolve_p4_command() -> str:
    executable = shutil.which('p4')
    if executable:
        return executable
    raise RuntimeError('p4 was not found on PATH.')


def build_command(executable: str, args: list[str]) -> list[str]:
    lowered = executable.lower()
    if lowered.endswith('.cmd') or lowered.endswith('.bat'):
        return ['cmd.exe', '/d', '/c', executable, *args]
    return [executable, *args]


def run_p4(executable: str, server: str, user: str, password: str, p4_args: list[str]) -> subprocess.CompletedProcess[str]:
    arguments = ['-p', server, '-u', user, *p4_args]

    env = os.environ.copy()
    if password.strip():
        env['P4PASSWD'] = password

    return subprocess.run(
        build_command(executable, arguments),
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        check=False,
        env=env,
    )


def parse_ztag_records(stdout: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line.startswith('... '):
            continue

        payload = line[4:]
        if ' ' not in payload:
            continue

        key, value = payload.split(' ', 1)
        if key == 'depotFile' and current:
            records.append(current)
            current = {}

        current[key] = value

    if current:
        records.append(current)

    return records
