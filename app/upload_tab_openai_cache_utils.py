from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .app_logging import app_log_exception

def openai_metadata_cache_path(app_dir: Path) -> Path:
    return app_dir / "openai_metadata_cache.json"


def load_openai_metadata_cache(cache_path: Path) -> dict[str, Any]:
    try:
        if not cache_path.exists():
            return {"version": 2, "items": {}}
        raw = cache_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"version": 2, "items": {}}
        if not isinstance(data.get("items"), dict):
            data["items"] = {}
        data["version"] = 2
        return data
    except Exception as exc:
        app_log_exception("OpenAI-Metadaten-Cache konnte nicht gelesen werden", exc, path=str(cache_path))
        return {"version": 2, "items": {}}


def save_openai_metadata_cache(cache_path: Path, data: dict[str, Any]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        items = data.get("items") if isinstance(data.get("items"), dict) else {}
        if len(items) > 200:
            ordered = sorted(items.items(), key=lambda item: str(item[1].get("created_at", "")))
            data["items"] = dict(ordered[-200:])
        cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        app_log_exception("OpenAI-Metadaten-Cache konnte nicht gespeichert werden", exc, path=str(cache_path))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload_file_fingerprint(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        resolved = Path(path).expanduser().resolve()
        stat = resolved.stat()
        return {
            "path": os.path.normcase(str(resolved)),
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "sha256": file_sha256(resolved),
        }
    except Exception:
        return None


def openai_metadata_cache_key(selected_file: Path | None, analysis_file: Path | None = None) -> str | None:
    selected_fp = upload_file_fingerprint(selected_file)
    if not selected_fp:
        return None
    analysis_fp = upload_file_fingerprint(analysis_file)
    parts = [f"selected:{selected_fp['sha256']}"]
    if analysis_fp and analysis_fp["sha256"] != selected_fp["sha256"]:
        parts.append(f"analysis:{analysis_fp['sha256']}")
    return "|".join(parts)


def cached_openai_metadata_for_key(cache: dict[str, Any], cache_key: str | None) -> dict[str, Any] | None:
    if not cache_key:
        return None
    items = cache.get("items") if isinstance(cache, dict) else {}
    if not isinstance(items, dict):
        return None
    cached = items.get(cache_key)
    if not isinstance(cached, dict):
        return None
    metadata = cached.get("metadata")
    if not isinstance(metadata, dict) or not any(str(value or "").strip() for value in metadata.values()):
        return None
    return cached


def add_openai_metadata_cache_entry(
    cache: dict[str, Any],
    cache_key: str | None,
    selected_file: Path | None,
    analysis_file: Path | None,
    metadata: dict[str, Any],
    usage: dict[str, Any] | None,
    model: str,
    now_iso: str,
) -> dict[str, Any]:
    if not cache_key or not metadata:
        return cache
    items = cache.setdefault("items", {})
    if not isinstance(items, dict):
        items = {}
        cache["items"] = items
    items[cache_key] = {
        "created_at": now_iso,
        "filename": selected_file.name if selected_file else "",
        "analysis_file": str(analysis_file or ""),
        "selected_fingerprint": upload_file_fingerprint(selected_file),
        "analysis_fingerprint": upload_file_fingerprint(analysis_file),
        "model": str(model or ""),
        "metadata": metadata,
        "usage": usage or {},
    }
    return cache
