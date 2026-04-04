from __future__ import annotations

import argparse
import concurrent.futures
from pathlib import Path
from typing import Any

from workflow_common import (
    DEFAULT_SOURCE_PRIORITY,
    build_pinterest_search_url,
    collect_tokens,
    download_file,
    fetch_pinterest_pin_details,
    guess_extension,
    is_low_signal_title,
    load_json,
    load_state,
    mark_topic_flags,
    project_slug,
    resolve_assets_config,
    save_json,
    save_state,
    set_step_state,
    source_rank,
    pinterest_image_quality,
    stable_slug,
    topic_id,
    upgrade_pinterest_image_url,
    utc_now_iso,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Curate normalized search results into selected references.")
    parser.add_argument("--plan", required=True, help="Path to design-plan.json")
    parser.add_argument("--search-results", required=True, help="Path to search-results.json")
    parser.add_argument("--output", required=True, help="Path to selected-refs.json")
    parser.add_argument("--state", help="Path to run-state.json")
    parser.add_argument("--vault-root", help="Override project.vault_root")
    parser.add_argument("--assets-dir", help="Override project.assets_dir")
    parser.add_argument("--assets-relative-dir", help="Override project.assets_dir_relative")
    parser.add_argument("--skip-download", action="store_true", help="Keep remote URLs only")
    parser.add_argument("--fallback-pick-count", type=int, default=3, help="Default refs to keep per topic")
    parser.add_argument("--detail-workers", type=int, default=4, help="Parallel Pinterest detail fetch workers")
    return parser


def parse_match_groups(topic: dict[str, Any]) -> list[set[str]]:
    groups: list[set[str]] = []
    for raw_group in topic.get("must_match_groups") or []:
        if isinstance(raw_group, list):
            tokens = collect_tokens(*raw_group)
        else:
            tokens = collect_tokens(raw_group)
        if tokens:
            groups.append(tokens)
    return groups


def analyze_entry(entry: dict[str, Any], topic: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(
        [
            str(entry.get("resolved_title") or ""),
            str(entry.get("title") or ""),
            str(entry.get("detail_title") or ""),
            str(entry.get("detail_description") or ""),
            str(entry.get("alt") or ""),
            str(entry.get("url") or ""),
            " ".join(entry.get("tags") or []),
        ]
    ).lower()
    detail_text = " ".join(
        [
            str(entry.get("detail_title") or ""),
            str(entry.get("detail_description") or ""),
        ]
    ).lower()
    is_pinterest = is_pinterest_entry(entry)
    image_quality = pinterest_image_quality(str(entry.get("resolved_image") or entry.get("image") or ""))
    topic_tokens = collect_tokens(
        topic.get("title"),
        topic.get("search_goal"),
        topic.get("why_it_matters"),
        topic.get("pinterest_query"),
    )
    must_match_tokens = collect_tokens(*(topic.get("must_match") or []))
    reject_tokens = collect_tokens(*(topic.get("reject_match") or []))
    must_match_groups = parse_match_groups(topic)

    topic_token_hits = sorted(token for token in topic_tokens if token in text)
    detail_token_hits = sorted(token for token in topic_tokens if detail_text and token in detail_text)
    must_match_hits = sorted(token for token in must_match_tokens if token in text)
    reject_hits = sorted(token for token in reject_tokens if token in text)
    matched_groups = []
    for index, group in enumerate(must_match_groups, start=1):
        hits = sorted(token for token in group if token in text)
        matched_groups.append(
            {
                "index": index,
                "tokens": sorted(group),
                "hits": hits,
                "matched": bool(hits),
            }
        )

    return {
        "text": text,
        "detail_text": detail_text,
        "is_pinterest": is_pinterest,
        "image_quality": image_quality,
        "topic_token_hits": topic_token_hits,
        "detail_token_hits": detail_token_hits,
        "must_match_hits": must_match_hits,
        "reject_hits": reject_hits,
        "matched_groups": matched_groups,
        "topic_token_hit_count": len(topic_token_hits),
        "detail_token_hit_count": len(detail_token_hits),
        "must_match_hit_count": len(must_match_hits),
        "reject_hit_count": len(reject_hits),
        "matched_group_count": sum(1 for group in matched_groups if group["matched"]),
        "match_group_count": len(matched_groups),
    }


def score_entry(entry: dict[str, Any], topic: dict[str, Any], source_priority: list[str]) -> float:
    analysis = analyze_entry(entry, topic)
    text = str(analysis["text"])
    detail_text = str(analysis["detail_text"])
    is_pinterest = bool(analysis["is_pinterest"])
    image_quality = int(analysis["image_quality"])
    topic_token_hits = analysis["topic_token_hits"]
    detail_token_hits = analysis["detail_token_hits"]
    must_match_hits = analysis["must_match_hits"]
    reject_hits = analysis["reject_hits"]
    matched_groups = analysis["matched_groups"]

    score = max(0, 40 - source_rank(str(entry.get("source")), source_priority) * 10)
    if entry.get("image"):
        score += 25
    if entry.get("url"):
        score += 10
    if entry.get("resolved_title") or entry.get("title"):
        score += 5

    raw_score = entry.get("score")
    if isinstance(raw_score, (int, float)):
        score += float(raw_score)

    for _ in topic_token_hits:
        score += 3
    for _ in detail_token_hits:
        score += 2

    if entry.get("source") == "tumblr/search" and not entry.get("tags"):
        score -= 5
    if not entry.get("image"):
        score -= 20
    if entry.get("detail_title"):
        score += 8
    if is_pinterest and image_quality >= 700:
        score += 8
    if is_pinterest and image_quality < 300:
        score -= 10
    resolved_title = str(entry.get("resolved_title") or "")
    if is_low_signal_title(resolved_title):
        score -= 18
    elif is_low_signal_title(str(entry.get("title") or "")):
        score -= 6
    if is_pinterest and not entry.get("detail_title"):
        score -= 12
    if is_pinterest and not topic_token_hits:
        score -= 12
    if must_match_hits:
        score += 4 * len(must_match_hits)
    elif topic.get("must_match"):
        score -= 18
    if reject_hits:
        score -= 24 + 4 * len(reject_hits)
    for group in matched_groups:
        if group["matched"]:
            score += 8
        else:
            score -= 18

    return score


def dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for entry in entries:
        key = str(entry.get("url") or entry.get("image") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def build_note(topic: dict[str, Any]) -> str:
    parts = []
    if topic.get("search_goal"):
        parts.append(f"用途：{topic['search_goal']}")
    if topic.get("why_it_matters"):
        parts.append(f"观察：{topic['why_it_matters']}")
    if not parts:
        parts.append("用途：这一组用于支撑该 topic block 的结构判断与后续图生图。")
    return "\n\n".join(parts)


def is_pinterest_entry(entry: dict[str, Any]) -> bool:
    source = str(entry.get("source") or "")
    url = str(entry.get("url") or "")
    return source == "pinterest/search" or "pinterest.com/pin/" in url


def enrich_entry(entry: dict[str, Any], detail_cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    enriched = dict(entry)
    enriched["search_title"] = entry.get("title")
    enriched["search_image"] = entry.get("image")

    resolved_title = str(entry.get("title") or "").strip() or None
    resolved_image = str(entry.get("image") or "").strip() or None
    detail_title = None
    detail_description = None
    detail_error = None

    if is_pinterest_entry(entry):
        pin_url = str(entry.get("url") or "").strip()
        detail: dict[str, Any] = {}
        if pin_url:
            detail = detail_cache.get(pin_url, {})
            if not detail:
                try:
                    detail = fetch_pinterest_pin_details(pin_url)
                except Exception as exc:
                    detail = {"error": str(exc)}
                detail_cache[pin_url] = detail

        detail_title = str(detail.get("title") or "").strip() or None
        detail_description = str(detail.get("description") or "").strip() or None
        detail_error = str(detail.get("error") or "").strip() or None
        detail_image = str(detail.get("image") or "").strip() or None

        if detail_title and not is_low_signal_title(detail_title):
            resolved_title = detail_title
        if detail_image:
            resolved_image = detail_image
        elif resolved_image:
            resolved_image = upgrade_pinterest_image_url(resolved_image)

    enriched["detail_title"] = detail_title
    enriched["detail_description"] = detail_description
    enriched["detail_fetch_error"] = detail_error
    enriched["resolved_title"] = resolved_title
    enriched["resolved_image"] = resolved_image
    return enriched


def prefetch_pinterest_details(entries: list[dict[str, Any]], max_workers: int) -> dict[str, dict[str, Any]]:
    pin_urls = []
    seen_urls: set[str] = set()
    for entry in entries:
        if not is_pinterest_entry(entry):
            continue
        pin_url = str(entry.get("url") or "").strip()
        if not pin_url or pin_url in seen_urls:
            continue
        seen_urls.add(pin_url)
        pin_urls.append(pin_url)

    if not pin_urls:
        return {}

    cache: dict[str, dict[str, Any]] = {}
    worker_count = max(1, min(max_workers, len(pin_urls)))

    def fetch_one(pin_url: str) -> tuple[str, dict[str, Any]]:
        try:
            return pin_url, fetch_pinterest_pin_details(pin_url)
        except Exception as exc:
            return pin_url, {"error": str(exc)}

    if worker_count == 1:
        for pin_url in pin_urls:
            url, detail = fetch_one(pin_url)
            cache[url] = detail
        return cache

    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(fetch_one, pin_url) for pin_url in pin_urls]
        for future in concurrent.futures.as_completed(futures):
            url, detail = future.result()
            cache[url] = detail
    return cache


def should_select_entry(entry: dict[str, Any], topic: dict[str, Any]) -> tuple[bool, list[str]]:
    selection = topic.get("selection") or {}
    reasons: list[str] = []

    min_score = selection.get("min_score")
    if isinstance(min_score, (int, float)) and float(entry.get("curation_score") or 0.0) < float(min_score):
        reasons.append(f"score<{float(min_score):g}")

    min_topic_hits = selection.get("min_topic_hits")
    if isinstance(min_topic_hits, int) and min_topic_hits > 0:
        if int(entry.get("topic_token_hit_count") or 0) < min_topic_hits:
            reasons.append(f"topic_hits<{min_topic_hits}")

    min_must_match_hits = selection.get("min_must_match_hits")
    if isinstance(min_must_match_hits, int) and min_must_match_hits > 0:
        if int(entry.get("must_match_hit_count") or 0) < min_must_match_hits:
            reasons.append(f"must_hits<{min_must_match_hits}")

    require_detail_title = bool(selection.get("require_detail_title"))
    if require_detail_title and not entry.get("detail_title"):
        reasons.append("missing_detail_title")

    require_pinterest_detail = bool(selection.get("require_pinterest_detail"))
    if require_pinterest_detail and is_pinterest_entry(entry) and not entry.get("detail_title"):
        reasons.append("missing_pinterest_detail")

    require_signal_title = bool(selection.get("require_signal_title"))
    if require_signal_title:
        titles = [entry.get("resolved_title"), entry.get("detail_title"), entry.get("search_title"), entry.get("title")]
        if all(is_low_signal_title(title) for title in titles):
            reasons.append("low_signal_title")

    reject_on_reject_match = selection.get("reject_on_reject_match")
    if reject_on_reject_match is None:
        reject_on_reject_match = bool(topic.get("reject_match"))
    if reject_on_reject_match and int(entry.get("reject_hit_count") or 0) > 0:
        reasons.append("reject_match")

    require_all_match_groups = selection.get("require_all_match_groups")
    if require_all_match_groups is None:
        require_all_match_groups = bool(topic.get("must_match_groups"))
    if require_all_match_groups:
        group_count = int(entry.get("match_group_count") or 0)
        matched_group_count = int(entry.get("matched_group_count") or 0)
        if group_count > 0 and matched_group_count < group_count:
            reasons.append("missing_match_group")

    return not reasons, reasons


def download_selected_reference(
    entry: dict[str, Any],
    destination_dir: Path,
    destination_relative_dir: str,
    project_slug_value: str,
    topic_slug: str,
    index: int,
) -> tuple[str | None, str | None]:
    image_url = entry.get("resolved_image") or entry.get("image")
    if not image_url:
        return None, "No image URL available"

    extension = guess_extension(str(image_url))
    filename = f"{project_slug_value}_ref_{topic_slug}_{index:02d}{extension}"
    destination = destination_dir / filename
    try:
        download_file(str(image_url), destination)
    except Exception as exc:
        return None, str(exc)

    local_path = f"{destination_relative_dir.rstrip('/')}/{filename}"
    return local_path, None


def main() -> None:
    args = build_parser().parse_args()
    plan = load_json(Path(args.plan))
    search_results = load_json(Path(args.search_results))
    slug = project_slug(plan)
    output_path = Path(args.output)
    state_path = Path(args.state) if args.state else output_path.with_name("run-state.json")
    state = load_state(state_path, slug)
    set_step_state(state, "ref-curator", "running", detail="Curating search results")
    save_state(state_path, state)

    source_priority = list(plan.get("source_priority") or DEFAULT_SOURCE_PRIORITY)
    project = plan.get("project", {})
    download_enabled = not args.skip_download
    assets_dir: Path | None = None
    assets_relative_dir: str | None = None
    if download_enabled:
        assets_dir, assets_relative_dir = resolve_assets_config(
            project,
            vault_root_override=args.vault_root,
            assets_dir_override=args.assets_dir,
            assets_relative_override=args.assets_relative_dir,
        )
        assets_dir.mkdir(parents=True, exist_ok=True)

    topics = {topic_id(topic): topic for topic in plan.get("topic_blocks") or []}
    topic_results = {item["id"]: item for item in search_results.get("topic_results") or []}

    curated_blocks = []
    all_entries = []
    for result in topic_results.values():
        all_entries.extend(dedupe_entries(result.get("entries") or []))
    detail_cache = prefetch_pinterest_details(all_entries, args.detail_workers)

    for current_topic_id, topic in topics.items():
        result = topic_results.get(current_topic_id, {})
        deduped_entries = dedupe_entries(result.get("entries") or [])
        scored_entries = []
        for entry in deduped_entries:
            scored = enrich_entry(entry, detail_cache)
            scored["curation_score"] = score_entry(scored, topic, source_priority)
            scored.update(analyze_entry(scored, topic))
            scored_entries.append(scored)

        scored_entries.sort(key=lambda item: (-float(item["curation_score"]), source_rank(str(item["source"]), source_priority), int(item["rank"])))

        selection = topic.get("selection") or {}
        pick_count = int(selection.get("max") or args.fallback_pick_count)
        selected = []
        filtered_out_count = 0
        for entry in scored_entries:
            keep, reasons = should_select_entry(entry, topic)
            entry["selection_reasons"] = reasons
            if not keep:
                filtered_out_count += 1
                continue
            if len(selected) >= pick_count:
                break
            index = len(selected) + 1
            selected_entry = {
                "title": entry.get("resolved_title") or entry.get("title"),
                "source": entry.get("source"),
                "origin_url": entry.get("url"),
                "image_url": entry.get("resolved_image") or entry.get("image"),
                "search_title": entry.get("search_title"),
                "search_image_url": entry.get("search_image"),
                "detail_title": entry.get("detail_title"),
                "detail_description": entry.get("detail_description"),
                "alt": entry.get("alt"),
                "tags": entry.get("tags") or [],
                "score": entry.get("curation_score"),
                "detail_fetch_error": entry.get("detail_fetch_error"),
                "topic_token_hits": entry.get("topic_token_hits") or [],
                "must_match_hits": entry.get("must_match_hits") or [],
                "reject_hits": entry.get("reject_hits") or [],
                "matched_groups": entry.get("matched_groups") or [],
                "local_path": None,
                "download_error": None,
            }
            if download_enabled and assets_dir and assets_relative_dir:
                local_path, download_error = download_selected_reference(
                    entry,
                    assets_dir,
                    assets_relative_dir,
                    slug,
                    stable_slug(current_topic_id, prefix="topic"),
                    index,
                )
                selected_entry["local_path"] = local_path
                selected_entry["download_error"] = download_error
            selected.append(selected_entry)

        pinterest_query = topic.get("pinterest_query") or result.get("pinterest_query") or topic.get("title")
        curated_blocks.append(
            {
                "id": current_topic_id,
                "title": topic.get("title") or current_topic_id,
                "note": build_note(topic),
                "link": {
                    "label": f"Pinterest: {pinterest_query}",
                    "url": build_pinterest_search_url(str(pinterest_query)),
                },
                "candidate_count": len(scored_entries),
                "filtered_out_count": filtered_out_count,
                "selected_count": len(selected),
                "selection_rules": selection,
                "references": selected,
            }
        )
        mark_topic_flags(state, current_topic_id, curated=bool(selected), selected_count=len(selected))

    payload = {
        "project_slug": slug,
        "project_title": project.get("title") or slug,
        "board_path": project.get("board_path"),
        "assets_dir": project.get("assets_dir"),
        "generator": project.get("generator") or "nano-banana",
        "language": project.get("language") or "zh-CN",
        "generated_at": utc_now_iso(),
        "style_summary": (plan.get("prompt_context") or {}).get("style_summary"),
        "must_preserve": (plan.get("prompt_context") or {}).get("must_preserve") or [],
        "topic_blocks": curated_blocks,
    }
    save_json(output_path, payload)

    detail = f"Curated {len(curated_blocks)} topic blocks"
    set_step_state(state, "ref-curator", "completed", detail=detail, artifacts=[str(output_path)])
    save_state(state_path, state)
    print(detail)


if __name__ == "__main__":
    main()
