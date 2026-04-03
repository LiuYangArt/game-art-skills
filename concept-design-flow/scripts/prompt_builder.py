from __future__ import annotations

import argparse
from pathlib import Path

from workflow_common import load_json, load_state, project_slug, save_json, save_state, set_step_state, utc_now_iso


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Nano Banana prompt pack from selected references.")
    parser.add_argument("--selected-refs", required=True, help="Path to selected-refs.json")
    parser.add_argument("--output", required=True, help="Path to prompt-pack.json")
    parser.add_argument("--state", help="Path to run-state.json")
    return parser


def compact_topic_titles(topic_blocks: list[dict]) -> str:
    names = [str(block.get("title") or "").split("/")[0].strip() for block in topic_blocks if block.get("title")]
    unique = []
    for name in names:
        if name and name not in unique:
            unique.append(name)
    return "、".join(unique)


def build_style_summary(selected_refs: dict) -> str:
    existing = selected_refs.get("style_summary")
    if existing:
        return str(existing)

    title = selected_refs.get("project_title") or selected_refs.get("project_slug") or "概念设计项目"
    topics = compact_topic_titles(selected_refs.get("topic_blocks") or [])
    return (
        f"整体方向是现代写实的 {title} 设计，优先吸收 {topics} 这些 topic block 里稳定、可转移的工程逻辑。"
        "视觉气质偏纪实摄影和工业写实，不做泛科幻装饰，不做没有功能依据的机械噪声。"
    )


def build_prompt_pack(selected_refs: dict) -> dict:
    title = selected_refs.get("project_title") or selected_refs.get("project_slug") or "概念设计项目"
    topics = compact_topic_titles(selected_refs.get("topic_blocks") or [])
    style_summary = build_style_summary(selected_refs)
    must_preserve = selected_refs.get("must_preserve") or [
        "输入草图或白盒里的整体轮廓、比例、镜头角度和主次体块",
        "已经确定的结构布局、设备落位与主要通道关系",
        "构图、视角、主体剪影和已锁定的功能区分区",
    ]

    sketch_to_image = (
        f"以输入草图作为唯一的构图和轮廓依据，严格保留 {title} 的整体剪影、比例关系、镜头角度和主要功能区布局。"
        f"把它转化成现代写实的高可信概念图，重点吸收 {topics} 的真实工程逻辑。"
        "材质应明确表现为喷漆钢板、防滑涂层、哑光雷达罩、液压结构和轻度服役痕迹。"
        "不要改变构图，不要加入无功能依据的科幻附件，不要做海报化夸张光效。"
    )

    whitebox_to_image = (
        f"把输入白盒或粗模 3D 体块当作硬约束来源，严格保留 {title} 的体量关系、主次结构、镜头视角和设备落位。"
        f"在不改构图的前提下，用 {topics} 这些参考图里已经验证过的结构逻辑去补齐细节。"
        "细节应包含真实的结构分缝、维护平台、栏杆、梯子、舱门、走线与设备基座，所有补充都必须有功能解释。"
    )

    detail_refinement = (
        f"把输入图片当作局部结构的严格参考，只细化与 {topics} 相关的工程细节和表面定义。"
        "保留原有轮廓、安装关系和机械连接逻辑，增强真实感、维护性和工业清晰度。"
        "不要替换原有设备类别，不要引入随机装饰件，不要把军舰设备做成玩具化道具。"
    )

    reusable_modules = {
        "主题模块": f"{title}、{topics}、真实海军工程逻辑、可维护的大平面体块",
        "材质模块": "喷漆钢板、防滑甲板、哑光雷达罩、液压结构、轻度盐迹与油污、克制做旧",
        "光照模块": "明亮阴天或硬日光、冷中性色、清晰阴影边缘、纪实摄影层次",
        "负面模块": "不要飞船化、不要无意义机械噪声、不要动漫化、不要海报式英雄镜头、不要夸张锈蚀",
    }

    rules = [
        "图生图时要同时提供文字 prompt 和输入图片。",
        "先写清楚必须保留的轮廓、比例、镜头与布局，再写清楚目标材质、光照和真实度。",
        "优先写具体结构与具体材质，不要只写抽象词，例如“更写实”“更酷”。",
        "如果要继续细化，先锁整体方向，再局部细化武器、舰岛、甲板设备等 topic。",
    ]

    return {
        "generator": selected_refs.get("generator") or "nano-banana",
        "language": selected_refs.get("language") or "zh-CN",
        "generated_at": utc_now_iso(),
        "style_summary": style_summary,
        "must_preserve": must_preserve,
        "rules": rules,
        "sketch_to_image": sketch_to_image,
        "whitebox_to_image": whitebox_to_image,
        "detail_refinement": detail_refinement,
        "reusable_modules": reusable_modules,
    }


def main() -> None:
    args = build_parser().parse_args()
    selected_refs_path = Path(args.selected_refs)
    output_path = Path(args.output)
    selected_refs = load_json(selected_refs_path)
    slug = str(selected_refs.get("project_slug") or project_slug(selected_refs))
    state_path = Path(args.state) if args.state else output_path.with_name("run-state.json")

    state = load_state(state_path, slug)
    set_step_state(state, "prompt-builder", "running", detail="Building prompt pack")
    save_state(state_path, state)

    prompt_pack = build_prompt_pack(selected_refs)
    save_json(output_path, prompt_pack)

    set_step_state(state, "prompt-builder", "completed", detail="Prompt pack generated", artifacts=[str(output_path)])
    save_state(state_path, state)
    print("Prompt pack generated")


if __name__ == "__main__":
    main()
