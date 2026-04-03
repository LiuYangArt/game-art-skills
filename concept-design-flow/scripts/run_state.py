from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflow_common import default_state, load_state, mark_topic_flags, save_state, set_step_state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect or update concept-design-flow run state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a new run-state.json file.")
    init_parser.add_argument("--file", required=True, help="Path to run-state.json")
    init_parser.add_argument("--project-slug", required=True, help="Project slug")

    status_parser = subparsers.add_parser("status", help="Print the current state JSON.")
    status_parser.add_argument("--file", required=True, help="Path to run-state.json")
    status_parser.add_argument("--project-slug", default="concept-project", help="Fallback project slug")

    step_parser = subparsers.add_parser("mark-step", help="Update one step entry.")
    step_parser.add_argument("--file", required=True, help="Path to run-state.json")
    step_parser.add_argument("--project-slug", default="concept-project", help="Fallback project slug")
    step_parser.add_argument("--step", required=True, help="Step name")
    step_parser.add_argument("--status", required=True, help="Step status")
    step_parser.add_argument("--detail", help="Optional detail text")
    step_parser.add_argument("--artifact", action="append", default=[], help="Artifact path to append")

    topic_parser = subparsers.add_parser("mark-topic", help="Update one topic status entry.")
    topic_parser.add_argument("--file", required=True, help="Path to run-state.json")
    topic_parser.add_argument("--project-slug", default="concept-project", help="Fallback project slug")
    topic_parser.add_argument("--topic", required=True, help="Topic id")
    topic_parser.add_argument("--flag", action="append", default=[], help="flag=value")
    return parser


def parse_flag_values(raw_flags: list[str]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for raw_flag in raw_flags:
        if "=" not in raw_flag:
            raise ValueError(f"Expected flag=value, got: {raw_flag}")
        key, value = raw_flag.split("=", 1)
        lowered = value.lower()
        if lowered in {"true", "false"}:
            parsed[key] = lowered == "true"
        else:
            parsed[key] = value
    return parsed


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    state_path = Path(args.file)

    if args.command == "init":
        state = default_state(args.project_slug)
        save_state(state_path, state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return

    state = load_state(state_path, args.project_slug)

    if args.command == "status":
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return

    if args.command == "mark-step":
        set_step_state(state, step=args.step, status=args.status, detail=args.detail, artifacts=args.artifact)
        save_state(state_path, state)
        print(json.dumps(state["steps"][args.step], ensure_ascii=False, indent=2))
        return

    if args.command == "mark-topic":
        flags = parse_flag_values(args.flag)
        mark_topic_flags(state, args.topic, **flags)
        save_state(state_path, state)
        print(json.dumps(state["topic_status"][args.topic], ensure_ascii=False, indent=2))
        return

    raise RuntimeError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
