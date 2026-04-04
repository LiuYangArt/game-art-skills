from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from workflow_common import load_json, load_state, mark_topic_flags, project_slug, save_json, save_state, set_step_state


SUMMARY_X = 120
SUMMARY_Y = -520
TOPIC_GROUP_WIDTH = 1320
TOPIC_GROUP_HEIGHT = 520
TOPIC_GROUP_GAP_X = 140
TOPIC_GROUP_GAP_Y = 140
TOPIC_START_X = 120
TOPIC_START_Y = 120
NOTE_WIDTH = 360
NOTE_HEIGHT = 300
IMAGE_WIDTH = 250
IMAGE_HEIGHT = 210


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a deterministic Obsidian canvas from selected references.")
    parser.add_argument("--selected-refs", required=True, help="Path to selected-refs.json")
    parser.add_argument("--output", required=True, help="Path to output .canvas file")
    parser.add_argument("--prompt-pack", help="Optional prompt-pack.json file")
    parser.add_argument("--state", help="Path to run-state.json")
    return parser


def node_id(prefix: str, *parts: object) -> str:
    suffix = "-".join(str(part) for part in parts)
    return f"{prefix}-{suffix}"


def build_summary_text(selected_refs: dict[str, Any]) -> str:
    title = selected_refs.get("project_title") or selected_refs.get("project_slug") or "Concept Board"
    style_summary = selected_refs.get("style_summary") or "该板面只保留已通过筛选、且能直接支持结构判断与图生图的 topic block。"
    return f"# {title} 参考板\n\n{style_summary}"


def build_topic_text(block: dict[str, Any]) -> str:
    lines = [f"## {block['title']}"]
    if block.get("note"):
        lines.append(str(block["note"]).strip())
    link = block.get("link") or {}
    if link.get("url"):
        label = link.get("label") or link["url"]
        lines.append(f"链接：\n[{label}]({link['url']})")
    return "\n\n".join(lines)


def prompt_nodes(prompt_pack: dict[str, Any], x: int, y: int) -> list[dict[str, Any]]:
    group = {
        "id": "prompt-pack-group",
        "type": "group",
        "x": x,
        "y": y,
        "width": 1180,
        "height": 2520,
        "color": "3",
        "label": "Nano Banana Prompt Pack",
    }
    nodes = [group]
    sections = [
        ("style", "## 风格沉淀\n" + str(prompt_pack.get("style_summary") or ""), 520, 360, x + 40, y + 40),
        (
            "rules",
            "## Nano Banana 写法要点\n" + "\n".join(f"- {item}" for item in prompt_pack.get("rules") or []),
            520,
            340,
            x + 620,
            y + 40,
        ),
        ("sketch", "## 草图图生图 Prompt\n" + str(prompt_pack.get("sketch_to_image") or ""), 1090, 420, x + 40, y + 420),
        ("whitebox", "## 白盒图生图 Prompt\n" + str(prompt_pack.get("whitebox_to_image") or ""), 1090, 420, x + 40, y + 870),
        ("detail", "## 局部细化 Prompt\n" + str(prompt_pack.get("detail_refinement") or ""), 1090, 320, x + 40, y + 1320),
        (
            "reuse",
            "## 可复用 Prompt 模块\n" + "\n".join(f"{key}：{value}" for key, value in (prompt_pack.get("reusable_modules") or {}).items()),
            1090,
            320,
            x + 40,
            y + 1670,
        ),
    ]
    for index, (section_id, text, width, height, node_x, node_y) in enumerate(sections, start=1):
        nodes.append(
            {
                "id": node_id("prompt", section_id, index),
                "type": "text",
                "text": text,
                "x": node_x,
                "y": node_y,
                "width": width,
                "height": height,
            }
        )
    return nodes


def main() -> None:
    args = build_parser().parse_args()
    selected_refs = load_json(Path(args.selected_refs))
    prompt_pack = load_json(Path(args.prompt_pack)) if args.prompt_pack else None
    output_path = Path(args.output)
    slug = str(selected_refs.get("project_slug") or project_slug(selected_refs))
    state_path = Path(args.state) if args.state else output_path.with_name("run-state.json")

    state = load_state(state_path, slug)
    set_step_state(state, "canvas-builder", "running", detail="Generating deterministic canvas")
    save_state(state_path, state)

    nodes: list[dict[str, Any]] = [
        {
            "id": "board-summary",
            "type": "text",
            "text": build_summary_text(selected_refs),
            "x": SUMMARY_X,
            "y": SUMMARY_Y,
            "width": 980,
            "height": 280,
        }
    ]
    edges: list[dict[str, Any]] = []

    blocks = list(selected_refs.get("topic_blocks") or [])
    for index, block in enumerate(blocks):
        row = index // 2
        column = index % 2
        group_x = TOPIC_START_X + column * (TOPIC_GROUP_WIDTH + TOPIC_GROUP_GAP_X)
        group_y = TOPIC_START_Y + row * (TOPIC_GROUP_HEIGHT + TOPIC_GROUP_GAP_Y)
        current_topic_id = str(block.get("id") or f"topic-{index + 1}")
        nodes.append(
            {
                "id": node_id("group", current_topic_id),
                "type": "group",
                "x": group_x,
                "y": group_y,
                "width": TOPIC_GROUP_WIDTH,
                "height": TOPIC_GROUP_HEIGHT,
                "color": str((index % 5) + 1),
                "label": block.get("title") or current_topic_id,
            }
        )
        nodes.append(
            {
                "id": node_id("note", current_topic_id),
                "type": "text",
                "text": build_topic_text(block),
                "x": group_x + 30,
                "y": group_y + 40,
                "width": NOTE_WIDTH,
                "height": NOTE_HEIGHT,
            }
        )

        local_refs = [item for item in block.get("references") or [] if item.get("local_path")]
        image_positions = [
            (group_x + 430, group_y + 40),
            (group_x + 700, group_y + 40),
            (group_x + 970, group_y + 40),
        ]
        for ref_index, (reference, (image_x, image_y)) in enumerate(zip(local_refs[:3], image_positions), start=1):
            nodes.append(
                {
                    "id": node_id("ref", current_topic_id, ref_index),
                    "type": "file",
                    "file": reference["local_path"],
                    "x": image_x,
                    "y": image_y,
                    "width": IMAGE_WIDTH,
                    "height": IMAGE_HEIGHT,
                }
            )
        mark_topic_flags(state, current_topic_id, on_canvas=bool(local_refs))

    if prompt_pack:
        prompt_x = TOPIC_START_X + 2 * (TOPIC_GROUP_WIDTH + TOPIC_GROUP_GAP_X) + 80
        nodes.extend(prompt_nodes(prompt_pack, prompt_x, SUMMARY_Y))

    canvas = {"nodes": nodes, "edges": edges}
    save_json(output_path, canvas)

    set_step_state(state, "canvas-builder", "completed", detail="Canvas generated", artifacts=[str(output_path)])
    save_state(state_path, state)
    print("Canvas generated")


if __name__ == "__main__":
    main()
