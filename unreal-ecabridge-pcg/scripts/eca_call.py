#!/usr/bin/env python3
"""Small JSON-RPC client for ECABridge MCP."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from typing import Any

DEFAULT_URL = "http://127.0.0.1:3000/mcp"


class ECABridgeError(RuntimeError):
    pass


def call_tool(tool: str, args: dict[str, Any] | None = None, *, url: str | None = None, timeout: int = 120) -> dict[str, Any]:
    endpoint = url or os.environ.get("ECABRIDGE_MCP_URL") or DEFAULT_URL
    body = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": 1,
        "params": {"name": tool, "arguments": args or {}},
    }
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except Exception as exc:
        raise ECABridgeError(f"Failed to call ECABridge tool {tool!r} at {endpoint}: {exc}") from exc

    if "error" in payload:
        raise ECABridgeError(json.dumps(payload["error"], ensure_ascii=False))
    return payload


def result_payload(response: dict[str, Any]) -> Any:
    result = response.get("result", {})
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content") or []
    if content and isinstance(content[0], dict) and "text" in content[0]:
        text = content[0]["text"]
        try:
            return json.loads(text)
        except Exception:
            return text
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Call one ECABridge MCP tool and print JSON.")
    parser.add_argument("tool")
    parser.add_argument("--args-json", default="{}", help="JSON object passed as tool arguments.")
    parser.add_argument("--url", default=None)
    parser.add_argument("--timeout", type=int, default=120)
    parsed = parser.parse_args()

    try:
        args = json.loads(parsed.args_json)
        if not isinstance(args, dict):
            raise ValueError("--args-json must decode to a JSON object")
        response = call_tool(parsed.tool, args, url=parsed.url, timeout=parsed.timeout)
        print(json.dumps(result_payload(response), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())