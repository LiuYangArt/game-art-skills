import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


VALID_RESOLUTIONS = {"1K", "2K", "4K"}
MIME_EXTENSION_MAP = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
}
FILE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an image with Yunwu API and save it to a local file."
    )
    parser.add_argument("--prompt", required=True, help="Text prompt for image generation.")
    parser.add_argument(
        "--resolution",
        default="1K",
        choices=sorted(VALID_RESOLUTIONS),
        help="Output resolution preset. Defaults to 1K.",
    )
    parser.add_argument(
        "--ratio",
        default="1:1",
        help="Aspect ratio string such as 1:1, 16:9, or 3:2. Defaults to 1:1.",
    )
    parser.add_argument(
        "--output",
        help="Optional output file path or directory path. Relative paths are resolved from --cwd.",
    )
    parser.add_argument(
        "--cwd",
        default=os.getcwd(),
        help="Base working directory used to resolve the default output directory and relative paths.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="HTTP timeout in seconds. Defaults to 120.",
    )
    return parser.parse_args()


def load_config(skill_dir: Path) -> dict:
    config_path = skill_dir / "config.local.json"
    if not config_path.exists():
        raise RuntimeError(f"Missing config file: {config_path}")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in config file: {config_path}") from exc

    if not isinstance(config, dict):
        raise RuntimeError(f"Config file must contain an object: {config_path}")

    for key in ("apiKey", "baseUrl", "model"):
        value = config.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"Config field '{key}' is missing or empty in: {config_path}")

    return {
        "apiKey": config["apiKey"].strip(),
        "baseUrl": config["baseUrl"].strip(),
        "model": config["model"].strip(),
    }


def join_url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def build_endpoint(base_url: str, model: str) -> str:
    if re.search(r":generateContent(?:\?|$)", base_url):
        return base_url
    return join_url(base_url, f"v1beta/models/{urllib.parse.quote(model, safe='')}:generateContent")


def build_request_body(prompt: str, resolution: str, ratio: str) -> dict:
    return {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "imageConfig": {
                "aspectRatio": ratio,
                "imageSize": resolution,
            }
        },
    }


def request_generation(config: dict, prompt: str, resolution: str, ratio: str, timeout: int) -> dict:
    url = build_endpoint(config["baseUrl"], config["model"])
    body = json.dumps(build_request_body(prompt, resolution, ratio)).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['apiKey']}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        if detail:
            raise RuntimeError(f"Yunwu HTTP {exc.code}: {detail}") from exc
        raise RuntimeError(f"Yunwu HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request to Yunwu failed: {exc.reason}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Yunwu returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Yunwu returned an unexpected response shape.")

    return payload


def extract_provider_error(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    if isinstance(error, dict):
        for key in ("message", "msg", "detail"):
            value = error.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("message", "msg", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def parse_image_payload(payload: dict) -> tuple[str, bytes]:
    provider_error = extract_provider_error(payload)
    if provider_error:
        raise RuntimeError(f"Yunwu error: {provider_error}")

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise RuntimeError("Yunwu response missing candidates[].")

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            inline_data = part.get("inlineData")
            if not isinstance(inline_data, dict):
                continue
            raw_data = inline_data.get("data")
            if not isinstance(raw_data, str) or not raw_data.strip():
                continue
            mime_type = inline_data.get("mimeType")
            if not isinstance(mime_type, str) or not mime_type.strip():
                mime_type = "image/png"
            try:
                image_bytes = base64.b64decode(raw_data)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("Yunwu returned invalid base64 image data.") from exc
            return mime_type.strip().lower(), image_bytes

    raise RuntimeError("Yunwu response has no inline image data.")


def sanitize_prompt(prompt: str) -> str:
    normalized = re.sub(r"\s+", "-", prompt.strip().lower())
    normalized = re.sub(r"[^a-z0-9\-_]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized[:48] or "image"


def extension_from_mime(mime_type: str) -> str:
    return MIME_EXTENSION_MAP.get(mime_type.lower(), ".png")


def resolve_output_path(cwd: Path, output: str | None, prompt: str, mime_type: str) -> Path:
    extension = extension_from_mime(mime_type)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    default_name = f"{sanitize_prompt(prompt)}-{timestamp}{extension}"

    if output is None or not output.strip():
        target_dir = cwd / "images"
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / default_name

    raw_output = output.strip()
    is_explicit_dir = raw_output.endswith(("/", "\\"))
    output_path = Path(raw_output)
    if not output_path.is_absolute():
        output_path = cwd / output_path

    if is_explicit_dir or output_path.exists() and output_path.is_dir():
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path / default_name

    if output_path.suffix.lower() in FILE_EXTENSIONS:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path

    if output_path.suffix:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path.with_suffix(extension)

    output_path.mkdir(parents=True, exist_ok=True)
    return output_path / default_name


def main() -> int:
    args = parse_args()
    skill_dir = Path(__file__).resolve().parents[1]
    cwd = Path(args.cwd).resolve()
    config = load_config(skill_dir)
    payload = request_generation(
        config=config,
        prompt=args.prompt,
        resolution=args.resolution,
        ratio=args.ratio,
        timeout=args.timeout,
    )
    mime_type, image_bytes = parse_image_payload(payload)
    output_path = resolve_output_path(
        cwd=cwd,
        output=args.output,
        prompt=args.prompt,
        mime_type=mime_type,
    )
    output_path.write_bytes(image_bytes)

    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "mime_type": mime_type,
                "resolution": args.resolution,
                "ratio": args.ratio,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
