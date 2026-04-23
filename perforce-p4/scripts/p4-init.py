#!/usr/bin/env python3

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--defaults-path", required=True)
    parser.add_argument("--connection-config-path", required=True)
    parser.add_argument("--p4-exe-path", default="")
    parser.add_argument("--server", default="")
    parser.add_argument("--user", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--project-stream", default="")
    parser.add_argument("--engine-stream", default="")
    parser.add_argument("--project-root", default="")
    parser.add_argument("--engine-root", default="")
    parser.add_argument("--project-client", default="")
    parser.add_argument("--engine-client", default="")
    parser.add_argument("--install-if-missing", action="store_true")
    parser.add_argument("--skip-login", action="store_true")
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--write-connection-config", action="store_true")
    parser.add_argument("--persist-password", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--what-if", action="store_true")
    return parser.parse_args()


def load_json(path: str) -> dict | None:
    candidate = Path(path)
    if not candidate.exists():
        return None
    with candidate.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_config_value(obj: dict | None, name: str):
    if not obj:
        return None
    return obj.get(name)


def get_stream_leaf(stream: str) -> str:
    if not stream:
        return ""
    return stream.rstrip("/").split("/")[-1]


def expand_workspace_pattern(pattern: str, user: str, leaf: str) -> str:
    if not pattern:
        return ""
    computer = os.environ.get("COMPUTERNAME", "")
    return pattern.replace("{user}", user).replace("{computer}", computer).replace("{leaf}", leaf)


def build_command(executable: str, args: list[str]) -> list[str]:
    lowered = executable.lower()
    if lowered.endswith(".cmd") or lowered.endswith(".bat"):
        return ["cmd.exe", "/d", "/c", executable, *args]
    return [executable, *args]


def run_process(executable: str, args: list[str], input_text: str | None = None, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        build_command(executable, args),
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.stderr and not quiet:
        sys.stderr.write(completed.stderr)
    return completed


def resolve_p4_command(explicit_path: str, winget_id: str, install_if_missing: bool, what_if: bool, what_if_actions: list[dict]) -> str:
    if explicit_path:
        resolved = Path(explicit_path)
        if not resolved.exists():
            raise RuntimeError(f"p4 executable was not found at: {explicit_path}")
        return str(resolved)

    discovered = shutil.which("p4")
    if discovered:
        return discovered

    if not install_if_missing:
        raise RuntimeError("p4 was not found on PATH. Re-run with -InstallIfMissing or install Perforce.P4V first.")

    package_id = winget_id or "Perforce.P4V"
    if what_if:
        what_if_actions.append(
            {
                "description": "Install P4V with winget",
                "target": package_id,
            }
        )
        discovered = shutil.which("p4")
        if discovered:
            return discovered
        raise RuntimeError("p4 was not found on PATH, and -WhatIf cannot complete onboarding without an installed p4 client.")

    completed = subprocess.run(
        ["winget", "install", "-e", "--id", package_id],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    if completed.returncode != 0:
        raise RuntimeError("winget install failed.")

    discovered = shutil.which("p4")
    if not discovered:
        raise RuntimeError("p4 is still unavailable after install attempt.")
    return discovered


def invoke_p4(executable: str, server: str, user: str, arguments: list[str], client_name: str = "", allow_failure: bool = False, quiet: bool = False, input_text: str | None = None) -> tuple[list[str], int]:
    command_args = ["-p", server, "-u", user]
    if client_name:
        command_args.extend(["-c", client_name])
    command_args.extend(arguments)
    completed = run_process(executable, command_args, input_text=input_text, quiet=quiet)
    lines = completed.stdout.splitlines()
    if not allow_failure and completed.returncode != 0:
        raise RuntimeError(f"p4 command failed ({completed.returncode}): {' '.join(command_args)}")
    return lines, completed.returncode


def assert_server_trust(executable: str, server: str, user: str) -> None:
    if not server.lower().startswith("ssl:"):
        return
    output, exit_code = invoke_p4(executable, server, user, ["trust", "-l"], allow_failure=True, quiet=True)
    if exit_code != 0:
        raise RuntimeError(f"Failed to inspect SSL trust for {server}. Run 'p4 -p {server} trust' after verifying the fingerprint, then retry.")
    trusted_server = server[4:]
    pattern = re.compile(rf"^{re.escape(trusted_server)}\b")
    if not any(pattern.search(line) for line in output):
        raise RuntimeError(f"SSL trust is not configured for {server}. Run 'p4 -p {server} trust' after verifying the fingerprint, then retry.")


def test_client_exists(executable: str, server: str, user: str, client_name: str) -> bool:
    output, exit_code = invoke_p4(executable, server, user, ["clients", "-e", client_name], allow_failure=True, quiet=True)
    if exit_code != 0:
        return False
    pattern = re.compile(rf"^Client\s+{re.escape(client_name)}\b")
    return any(pattern.search(line) for line in output)


def assert_root_ready(root_path: str, force: bool) -> None:
    if not root_path:
        raise RuntimeError("Workspace root is required.")
    candidate = Path(root_path)
    if not candidate.exists():
        return
    try:
        next(candidate.iterdir())
    except StopIteration:
        return
    if not force:
        raise RuntimeError(f"Workspace root is not empty: {root_path}. Re-run with -Force only after confirming it is safe.")


def assert_stream_exists(executable: str, server: str, user: str, stream: str) -> None:
    if not stream:
        return
    _, exit_code = invoke_p4(executable, server, user, ["stream", "-o", stream], allow_failure=True, quiet=True)
    if exit_code != 0:
        raise RuntimeError(f"Stream does not exist or is not accessible: {stream}")


def create_stream_workspace(executable: str, server: str, user: str, stream: str, client_name: str, root_path: str, label: str, do_sync: bool, force: bool, what_if: bool, what_if_actions: list[dict]) -> dict | None:
    if not stream:
        return None

    assert_stream_exists(executable, server, user, stream)
    assert_root_ready(root_path, force)

    if what_if:
        what_if_actions.append(
            {
                "description": f"Create {label} workspace for {stream} at {root_path}",
                "target": client_name,
            }
        )
        return None

    if test_client_exists(executable, server, user, client_name) and not force:
        raise RuntimeError(f"Workspace already exists: {client_name}. Re-run with -Force only after confirming overwrite is intended.")

    Path(root_path).mkdir(parents=True, exist_ok=True)

    spec_lines, _ = invoke_p4(executable, server, user, ["client", "-S", stream, "-o", client_name])
    spec_text = "\n".join(spec_lines)
    if not re.search(r"(?m)^Root:\s+", spec_text):
        raise RuntimeError(f"Generated client spec for {client_name} does not contain a Root field.")
    spec_text = re.sub(r"(?m)^Root:\s+.*$", lambda _: f"Root:\t{root_path}", spec_text)
    _, exit_code = invoke_p4(executable, server, user, ["client", "-i"], input_text=spec_text, allow_failure=True)
    if exit_code != 0:
        raise RuntimeError(f"Failed to create workspace {client_name}")

    if do_sync:
        _, exit_code = invoke_p4(executable, server, user, ["sync"], client_name=client_name, allow_failure=True)
        if exit_code != 0:
            raise RuntimeError(f"Initial sync failed for workspace {client_name}")

    return {
        "stream": stream,
        "client": client_name,
        "root": root_path,
        "synced": bool(do_sync),
    }


def maybe_login(executable: str, server: str, user: str, password: str, skip_login: bool, what_if: bool, what_if_actions: list[dict], warnings: list[str]) -> None:
    if skip_login:
        return
    if not password:
        warnings.append("No password provided. The script will rely on an existing p4 login ticket.")
        return
    if what_if:
        what_if_actions.append(
            {
                "description": "Run p4 login",
                "target": f"{user}@{server}",
            }
        )
        return
    _, exit_code = invoke_p4(executable, server, user, ["login"], allow_failure=True, input_text=password)
    if exit_code != 0:
        raise RuntimeError("p4 login failed.")


def maybe_write_connection_config(path: str, server: str, user: str, password: str, write_connection_config: bool, persist_password: bool, what_if: bool, what_if_actions: list[dict]) -> None:
    if not write_connection_config:
        return
    if what_if:
        what_if_actions.append(
            {
                "description": "Write local p4 connection config",
                "target": path,
            }
        )
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "server": server,
        "user": user,
        "password": password if persist_password else "",
    }
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
        handle.write("\n")


def main() -> int:
    args = parse_args()
    defaults = load_json(args.defaults_path) or {}
    recommended_roots = get_config_value(defaults, "recommendedRoots") or {}
    workspace_pattern = get_config_value(defaults, "workspacePattern") or {}
    install = get_config_value(defaults, "install") or {}

    server = args.server or get_config_value(defaults, "server") or ""
    if not server:
        raise RuntimeError("Server is required. Provide -Server or supply it from a private onboarding document or local config.")
    if not args.user:
        raise RuntimeError("User is required.")
    if not args.project_stream:
        raise RuntimeError("ProjectStream is required.")

    project_leaf = get_stream_leaf(args.project_stream)
    engine_leaf = get_stream_leaf(args.engine_stream)

    project_root = args.project_root
    if not project_root:
        project_base = get_config_value(recommended_roots, "project") or r"D:\Perforce\Project"
        project_root = str(Path(project_base) / project_leaf)

    engine_root = args.engine_root
    if args.engine_stream and not engine_root:
        engine_base = get_config_value(recommended_roots, "engine") or r"D:\Perforce\Engine"
        engine_root = str(Path(engine_base) / engine_leaf)

    project_client = args.project_client
    if not project_client:
        pattern = get_config_value(workspace_pattern, "project") or "{user}_{computer}_{leaf}"
        project_client = expand_workspace_pattern(pattern, args.user, project_leaf)

    engine_client = args.engine_client
    if args.engine_stream and not engine_client:
        pattern = get_config_value(workspace_pattern, "engine") or "{user}_{computer}_Engine_{leaf}"
        engine_client = expand_workspace_pattern(pattern, args.user, engine_leaf)

    warnings: list[str] = []
    what_if_actions: list[dict] = []

    winget_id = get_config_value(install, "wingetId") or "Perforce.P4V"
    p4_executable = resolve_p4_command(args.p4_exe_path, winget_id, args.install_if_missing, args.what_if, what_if_actions)
    assert_server_trust(p4_executable, server, args.user)
    maybe_login(p4_executable, server, args.user, args.password, args.skip_login, args.what_if, what_if_actions, warnings)

    if args.sync:
        warnings.append("Command-line sync can take a long time without clear progress. Prefer opening the workspace in P4V unless the user explicitly requested CLI sync.")

    project_workspace = create_stream_workspace(
        executable=p4_executable,
        server=server,
        user=args.user,
        stream=args.project_stream,
        client_name=project_client,
        root_path=project_root,
        label="project",
        do_sync=args.sync,
        force=args.force,
        what_if=args.what_if,
        what_if_actions=what_if_actions,
    )

    engine_workspace = None
    if args.engine_stream:
        engine_workspace = create_stream_workspace(
            executable=p4_executable,
            server=server,
            user=args.user,
            stream=args.engine_stream,
            client_name=engine_client,
            root_path=engine_root,
            label="engine",
            do_sync=args.sync,
            force=args.force,
            what_if=args.what_if,
            what_if_actions=what_if_actions,
        )

    maybe_write_connection_config(
        path=args.connection_config_path,
        server=server,
        user=args.user,
        password=args.password,
        write_connection_config=args.write_connection_config,
        persist_password=args.persist_password,
        what_if=args.what_if,
        what_if_actions=what_if_actions,
    )

    result = {
        "p4ExePath": p4_executable,
        "server": server,
        "user": args.user,
        "projectStream": args.project_stream,
        "projectRoot": project_root,
        "projectClient": project_client,
        "projectWorkspaceCreated": project_workspace is not None,
        "engineStream": args.engine_stream,
        "engineRoot": engine_root,
        "engineClient": engine_client,
        "engineWorkspaceCreated": engine_workspace is not None,
        "wroteConnectionConfig": bool(args.write_connection_config and not args.what_if),
        "persistedPassword": bool(args.persist_password),
        "syncRequested": bool(args.sync),
        "recommendedNextStep": "CLI sync completed or was explicitly requested."
        if args.sync
        else "Open the workspace in P4V and run Get Latest there unless the user explicitly wants CLI sync.",
        "warnings": warnings,
        "whatIfActions": what_if_actions,
    }
    json.dump(result, sys.stdout, ensure_ascii=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
