from __future__ import annotations

import argparse
import concurrent.futures
from pathlib import Path
from typing import Any

from workflow_common import (
    DEFAULT_SOURCE_PRIORITY,
    build_pinterest_search_url,
    load_json,
    load_state,
    mark_topic_flags,
    project_slug,
    run_json_command,
    save_json,
    save_state,
    set_step_state,
    source_rank,
    topic_id,
    utc_now_iso,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bb-browser topic-block searches and save normalized JSON.")
    parser.add_argument("--plan", required=True, help="Path to design-plan.json")
    parser.add_argument("--output", required=True, help="Path to search-results.json")
    parser.add_argument("--state", help="Path to run-state.json")
    parser.add_argument("--max-workers", type=int, default=1, help="Parallel bb-browser query workers")
    parser.add_argument("--default-count", type=int, default=12, help="Fallback result count per query")
    return parser


def topic_queries(topic: dict[str, Any], source_priority: list[str], default_count: int) -> list[dict[str, Any]]:
    queries = list(topic.get("queries") or [])
    if queries:
        return queries

    fallback: list[dict[str, Any]] = []
    if topic.get("pinterest_query"):
        fallback.append({"source": "pinterest/search", "query": topic["pinterest_query"], "count": default_count})
    for source in source_priority[1:]:
        backup_key = f"{source.split('/')[0]}_query"
        if topic.get(backup_key):
            fallback.append({"source": source, "query": topic[backup_key], "count": default_count})
    return fallback


def build_command(query_spec: dict[str, Any], default_count: int) -> list[str]:
    source = str(query_spec.get("source") or query_spec.get("adapter") or "")
    query = str(query_spec.get("query") or "").strip()
    if not source or not query:
        raise ValueError(f"Each query needs source and query. got={query_spec!r}")

    command = [
        "bb-browser",
        "site",
        source,
        query,
        "--count",
        str(query_spec.get("count") or default_count),
        "--json",
    ]
    if query_spec.get("type"):
        command.extend(["--type", str(query_spec["type"])])
    return command


def run_query(job: dict[str, Any], default_count: int) -> dict[str, Any]:
    command = build_command(job["query_spec"], default_count)
    response = run_json_command(command)
    query_spec = job["query_spec"]

    run_record = {
        "topic_id": job["topic_id"],
        "topic_title": job["topic_title"],
        "source": query_spec.get("source") or query_spec.get("adapter"),
        "query": query_spec.get("query"),
        "count_requested": query_spec.get("count") or default_count,
        "success": bool(response.get("success")),
        "error": response.get("error"),
        "hint": response.get("hint"),
        "returned_count": 0,
        "entries": [],
    }

    if not response.get("success"):
        return run_record

    payload = response.get("data") or {}
    results = payload.get("results") or []
    entries = []
    for index, item in enumerate(results, start=1):
        entries.append(
            {
                "source": run_record["source"],
                "query": run_record["query"],
                "rank": index,
                "title": item.get("title"),
                "url": item.get("url"),
                "image": item.get("image"),
                "alt": item.get("alt"),
                "blog": item.get("blog"),
                "tags": item.get("tags") or [],
                "score": item.get("score"),
                "raw": item,
            }
        )
    run_record["returned_count"] = len(entries)
    run_record["entries"] = entries
    return run_record


def bb_browser_preflight() -> dict[str, Any]:
    return run_json_command(["bb-browser", "tab", "list", "--json"])


def main() -> None:
    args = build_parser().parse_args()
    plan_path = Path(args.plan)
    output_path = Path(args.output)

    plan = load_json(plan_path)
    slug = project_slug(plan)
    state_path = Path(args.state) if args.state else output_path.with_name("run-state.json")
    state = load_state(state_path, slug)
    set_step_state(state, "search-runner", "running", detail="Running bb-browser topic searches")
    save_state(state_path, state)

    source_priority = list(plan.get("source_priority") or DEFAULT_SOURCE_PRIORITY)
    preflight = bb_browser_preflight()
    if not preflight.get("success"):
        payload = {
            "project_slug": slug,
            "generated_at": utc_now_iso(),
            "source_priority": source_priority,
            "topic_results": [],
            "errors": [
                {
                    "stage": "bb-browser-preflight",
                    "error": preflight.get("error"),
                    "hint": preflight.get("hint"),
                }
            ],
        }
        save_json(output_path, payload)
        detail = "bb-browser preflight failed. Check Chrome/CDP connection before running search."
        set_step_state(state, "search-runner", "blocked", detail=detail, artifacts=[str(output_path)])
        save_state(state_path, state)
        print(detail)
        return

    jobs: list[dict[str, Any]] = []
    topics_by_id: dict[str, dict[str, Any]] = {}
    for topic in plan.get("topic_blocks") or []:
        current_topic_id = topic_id(topic)
        topics_by_id[current_topic_id] = topic
        for query_spec in topic_queries(topic, source_priority, args.default_count):
            jobs.append(
                {
                    "topic_id": current_topic_id,
                    "topic_title": topic.get("title") or current_topic_id,
                    "query_spec": query_spec,
                }
            )

    if not jobs:
        raise ValueError("No topic queries were found in design-plan.json")

    run_results: list[dict[str, Any]] = []
    if args.max_workers <= 1:
        for job in jobs:
            run_results.append(run_query(job, args.default_count))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            future_map = {executor.submit(run_query, job, args.default_count): job for job in jobs}
            for future in concurrent.futures.as_completed(future_map):
                run_results.append(future.result())

    topic_results = []
    errors = []
    for current_topic_id, topic in topics_by_id.items():
        topic_runs = [item for item in run_results if item["topic_id"] == current_topic_id]
        entries = []
        for run in topic_runs:
            if run["success"]:
                entries.extend(run["entries"])
            else:
                errors.append(
                    {
                        "topic_id": current_topic_id,
                        "topic_title": topic.get("title") or current_topic_id,
                        "source": run["source"],
                        "query": run["query"],
                        "error": run["error"],
                        "hint": run["hint"],
                    }
                )

        entries.sort(key=lambda item: (source_rank(str(item["source"]), source_priority), int(item["rank"])))
        topic_results.append(
            {
                "id": current_topic_id,
                "title": topic.get("title") or current_topic_id,
                "search_goal": topic.get("search_goal"),
                "why_it_matters": topic.get("why_it_matters"),
                "pinterest_query": topic.get("pinterest_query"),
                "pinterest_link": build_pinterest_search_url(str(topic.get("pinterest_query") or "")) if topic.get("pinterest_query") else None,
                "runs": [
                    {key: value for key, value in run.items() if key != "entries"}
                    for run in sorted(topic_runs, key=lambda item: source_rank(str(item["source"]), source_priority))
                ],
                "entries": entries,
            }
        )
        mark_topic_flags(state, current_topic_id, searched=bool(entries), search_errors=bool([run for run in topic_runs if not run["success"]]))

    topic_results.sort(key=lambda item: item["title"])
    payload = {
        "project_slug": slug,
        "generated_at": utc_now_iso(),
        "source_priority": source_priority,
        "topic_results": topic_results,
        "errors": errors,
    }
    save_json(output_path, payload)

    detail = f"Completed {len(topic_results)} topics with {len(errors)} source errors"
    set_step_state(state, "search-runner", "completed", detail=detail, artifacts=[str(output_path)])
    save_state(state_path, state)
    print(detail)


if __name__ == "__main__":
    main()
