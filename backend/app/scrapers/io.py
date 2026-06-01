import asyncio
import json
import os
from pathlib import Path
from typing import Any

DATA_DIR = os.getenv("DATA_DIR", "data")

_LOCKS: dict[str, asyncio.Lock] = {}


def get_file_lock(output_file: str) -> asyncio.Lock:
    if output_file not in _LOCKS:
        _LOCKS[output_file] = asyncio.Lock()
    return _LOCKS[output_file]


def resolve_path(output_file: str) -> str:
    if os.path.isabs(output_file):
        return output_file
    if output_file.startswith("/app/"):
        return output_file
    if Path(output_file).exists():
        return output_file
    base = Path(DATA_DIR)
    name = Path(output_file).name
    base.mkdir(parents=True, exist_ok=True)
    return str(base / name)


def load_deals(output_file: str) -> list[dict[str, Any]]:
    path = resolve_path(output_file)
    if not Path(path).exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "deals" in data:
            return list(data["deals"])
        return []
    except (json.JSONDecodeError, OSError):
        return []


def save_deals(output_file: str, deals: list[dict[str, Any]]) -> None:
    path = resolve_path(output_file)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(deals, f, ensure_ascii=False, indent=2)


def merge_deals_by_link(existing: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_link: dict[str, dict[str, Any]] = {}
    for d in existing:
        link = d.get("link")
        if link:
            by_link[link] = d
    for d in new:
        link = d.get("link")
        if link:
            by_link[link] = d
    return list(by_link.values())
