from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_PRIORITY = [
    "pinterest/search",
    "huaban/search",
    "tumblr/search",
]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
LOW_SIGNAL_TITLES = {
    "oops!",
    "selection",
    "sélection",
    "untitled",
    "未命名",
    "收藏到",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_posix(path_value: str) -> str:
    return path_value.replace("\\", "/")


def stable_slug(value: str, prefix: str = "item") -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if slug:
        return slug
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{digest}"


def topic_id(topic: dict[str, Any]) -> str:
    raw = str(topic.get("id") or topic.get("title") or topic.get("pinterest_query") or "topic")
    return stable_slug(raw, prefix="topic")


def build_pinterest_search_url(query: str) -> str:
    return f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(query)}"


def collect_tokens(*values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        text = str(value or "").strip().lower()
        if not text:
            continue
        for token in re.split(r"[\s,;:/|()\\-]+", text):
            if len(token) >= 2:
                tokens.add(token)
        if any("\u4e00" <= char <= "\u9fff" for char in text):
            tokens.add(text)
    return tokens


def source_rank(source: str, priority: list[str]) -> int:
    try:
        return priority.index(source)
    except ValueError:
        return len(priority)


def run_json_command(command: list[str]) -> dict[str, Any]:
    command = resolve_command(command)
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {command[0]}") from exc

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    payload = stdout or stderr
    if not payload:
        raise RuntimeError(f"Command produced no output: {' '.join(command)}")

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Command did not return JSON. exit={completed.returncode} stdout={stdout!r} stderr={stderr!r}"
        ) from exc

    if completed.returncode != 0 and parsed.get("success") is not False:
        parsed["success"] = False
        parsed.setdefault("error", stderr or f"Command failed with exit code {completed.returncode}")

    return parsed


def run_text_command(command: list[str]) -> str:
    command = resolve_command(command)
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {command[0]}") from exc

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}: {' '.join(command)} stderr={stderr!r}"
        )
    if stdout:
        return stdout
    if stderr:
        return stderr
    raise RuntimeError(f"Command produced no text output: {' '.join(command)}")


def resolve_command(command: list[str]) -> list[str]:
    executable = command[0]
    candidates = [executable]
    if executable == "bb-browser":
        npm_dir = Path.home() / "AppData" / "Roaming" / "npm"
        candidates.extend(
            [
                "bb-browser.cmd",
                str(npm_dir / "bb-browser.cmd"),
                str(npm_dir / "bb-browser"),
            ]
        )

    for candidate in candidates:
        if Path(candidate).is_file():
            return [candidate, *command[1:]]
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved, *command[1:]]

    raise RuntimeError(f"Command not found: {executable}. PATH={os.environ.get('PATH', '')}")


def guess_extension(url: str | None) -> str:
    if not url:
        return ".jpg"
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return suffix
    return ".jpg"


def download_file(url: str, destination: Path, timeout: int = 30) -> None:
    ensure_parent(destination)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        destination.write_bytes(response.read())


def normalize_whitespace(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def strip_html_tags(value: str | None) -> str:
    text = str(value or "")
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize_whitespace(html.unescape(text))


def is_low_signal_title(value: str | None) -> bool:
    text = normalize_whitespace(value).lower()
    if not text:
        return True
    if text in LOW_SIGNAL_TITLES:
        return True
    if text.startswith(("收藏到", "saved to ", "save to ")):
        return True
    return any(
        marker in text
        for marker in (
            "oops",
            "未命名",
            "image may contain",
            "pin on pinterest",
            "pinterest",
            "facebook",
            "stock photo",
            "views ·",
            "reactions",
            "ebay",
            "amazon.com",
        )
    )


def pinterest_image_quality(url: str | None) -> int:
    if not url or "i.pinimg.com" not in str(url):
        return 0

    path_parts = [part for part in urllib.parse.urlparse(str(url)).path.split("/") if part]
    if not path_parts:
        return 0

    size_token = path_parts[0].lower()
    if size_token == "originals":
        return 5000
    if size_token == "236x":
        return 236
    if size_token == "474x":
        return 474
    if size_token == "564x":
        return 564
    if size_token == "736x":
        return 736
    if size_token == "1200x":
        return 1200
    if size_token.endswith("_rs"):
        match = re.match(r"(\d+)x", size_token)
        if match:
            return int(match.group(1))

    match = re.match(r"(\d+)x", size_token)
    if match:
        return int(match.group(1))
    return 0


def upgrade_pinterest_image_url(url: str | None) -> str | None:
    if not url:
        return url
    parsed = urllib.parse.urlparse(str(url))
    if "i.pinimg.com" not in parsed.netloc:
        return str(url)

    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        return str(url)

    size_token = path_parts[0].lower()
    if size_token in {"236x", "474x", "564x"} or size_token.endswith("_rs"):
        path_parts[0] = "736x"
        new_path = "/" + "/".join(path_parts)
        return urllib.parse.urlunparse(parsed._replace(path=new_path))
    return str(url)


def extract_best_pinterest_image_url(html_text: str) -> str | None:
    candidates: list[str] = []
    snippets = []

    closeup_match = re.search(
        r'data-test-id="closeup-image-main".{0,4000}?</div>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if closeup_match:
        snippets.append(closeup_match.group(0))

    meta_match = re.search(
        r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
        html_text,
        flags=re.IGNORECASE,
    )
    if meta_match:
        candidates.append(html.unescape(meta_match.group(1)).replace("\\/", "/"))

    if not snippets:
        snippets.append(html_text)

    url_pattern = re.compile(r"https://i\.pinimg\.com/[^\s\"'<>]+", flags=re.IGNORECASE)
    for snippet in snippets:
        for match in url_pattern.findall(snippet):
            candidates.append(html.unescape(match).replace("\\/", "/").rstrip(","))

    unique_candidates = []
    for candidate in candidates:
        if candidate and candidate not in unique_candidates:
            unique_candidates.append(candidate)

    if not unique_candidates:
        return None

    return max(unique_candidates, key=pinterest_image_quality)


def extract_pinterest_title(html_text: str) -> str | None:
    patterns = [
        r'data-test-id="pin-title-wrapper"[^>]*>.*?<h1[^>]*>(.*?)</h1>',
        r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
        r"<title[^>]*>(.*?)</title>",
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        title = strip_html_tags(match.group(1))
        title = re.sub(r"\s*\|\s*Pinterest.*$", "", title, flags=re.IGNORECASE)
        if title:
            return title
    return None


def extract_pinterest_description(html_text: str) -> str | None:
    patterns = [
        r'data-test-id="richPinInformation-description"[^>]*>(.*?)</span>',
        r'<meta[^>]+name="description"[^>]+content="([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        description = strip_html_tags(match.group(1))
        if description:
            return description
    return None


def fetch_pinterest_pin_details(pin_url: str) -> dict[str, Any]:
    html_text = run_text_command(["bb-browser", "fetch", pin_url])
    image_url = extract_best_pinterest_image_url(html_text)
    return {
        "title": extract_pinterest_title(html_text),
        "description": extract_pinterest_description(html_text),
        "image": image_url,
    }


def default_state(project_slug: str) -> dict[str, Any]:
    return {
        "project_slug": project_slug,
        "updated_at": utc_now_iso(),
        "steps": {},
        "topic_status": {},
        "artifacts": [],
    }


def load_state(path: Path, project_slug: str) -> dict[str, Any]:
    if path.exists():
        state = load_json(path)
    else:
        state = default_state(project_slug)
    state.setdefault("project_slug", project_slug)
    state.setdefault("steps", {})
    state.setdefault("topic_status", {})
    state.setdefault("artifacts", [])
    state["updated_at"] = utc_now_iso()
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now_iso()
    save_json(path, state)


def set_step_state(
    state: dict[str, Any],
    step: str,
    status: str,
    detail: str | None = None,
    artifacts: list[str] | None = None,
) -> None:
    step_record = state["steps"].setdefault(step, {})
    step_record["status"] = status
    step_record["updated_at"] = utc_now_iso()
    if detail:
        step_record["detail"] = detail
    if artifacts:
        existing = step_record.setdefault("artifacts", [])
        for artifact in artifacts:
            if artifact not in existing:
                existing.append(artifact)
            if artifact not in state["artifacts"]:
                state["artifacts"].append(artifact)


def mark_topic_flags(state: dict[str, Any], topic: str, **flags: Any) -> None:
    topic_record = state["topic_status"].setdefault(topic, {})
    topic_record.update(flags)
    topic_record["updated_at"] = utc_now_iso()


def resolve_assets_config(
    project: dict[str, Any],
    vault_root_override: str | None = None,
    assets_dir_override: str | None = None,
    assets_relative_override: str | None = None,
) -> tuple[Path, str]:
    assets_dir_value = assets_dir_override or project.get("assets_dir")
    if not assets_dir_value:
        raise ValueError("project.assets_dir is required")

    assets_dir_path = Path(assets_dir_value).expanduser()
    if assets_dir_path.is_absolute():
        relative_dir = assets_relative_override or project.get("assets_dir_relative")
        if not relative_dir:
            raise ValueError("project.assets_dir_relative is required when assets_dir is absolute")
        return assets_dir_path, normalize_posix(relative_dir)

    vault_root_value = vault_root_override or project.get("vault_root")
    if not vault_root_value:
        raise ValueError("project.vault_root is required when assets_dir is relative")

    vault_root_path = Path(vault_root_value).expanduser()
    return vault_root_path / assets_dir_path, normalize_posix(str(assets_dir_path))


def project_slug(document: dict[str, Any]) -> str:
    project = document.get("project", {})
    raw = str(project.get("slug") or project.get("title") or document.get("project_slug") or "concept-project")
    return stable_slug(raw, prefix="project")
