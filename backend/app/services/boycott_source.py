"""Boykot markaları için çoklu kaynaklı liste yükleyici."""
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

_LOCAL_PATH = Path(__file__).parent.parent.parent / "data" / "boycott_brands.json"
_CACHE_TTL_SEC = int(os.getenv("BOYCOTT_CACHE_TTL_SEC", "21600"))  # 6 saat
_REMOTE_URL = os.getenv("BOYCOTT_BRANDS_URL", "").strip()
_REMOTE_TIMEOUT = float(os.getenv("BOYCOTT_FETCH_TIMEOUT_SEC", "5"))

_cache: dict[str, Any] = {"data": None, "ts": 0.0, "source": "uninitialized"}


def _load_local() -> dict[str, Any]:
    with open(_LOCAL_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["source"] = data.get("source", "local file")
    return data


def _fetch_remote(url: str) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MultiScout/1.0"})
        with urllib.request.urlopen(req, timeout=_REMOTE_TIMEOUT) as resp:
            if resp.status != 200:
                return None
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        # Liste formatında geliyorsa categories sarmala
        if "brands" in data and isinstance(data["brands"], list) and "categories" not in data:
            data = {
                "version": data.get("version", "remote"),
                "categories": {"remote": {"label": "Remote", "parent": "", "brands": data["brands"]}},
                "excluded_keywords": data.get("excluded_keywords", []),
            }
        data["source"] = url
        return data
    except Exception as e:
        print(f"[BOYCOTT] Remote fetch failed: {e}", flush=True)
        return None


def get_boycott_data(force_refresh: bool = False) -> dict[str, Any]:
    """Return boycott config; remote varsa onu cache'leyerek getir, yoksa local fallback."""
    now = time.time()
    fresh = (now - _cache["ts"]) < _CACHE_TTL_SEC
    if not force_refresh and fresh and _cache["data"] is not None:
        return _cache["data"]

    data: dict[str, Any] | None = None
    if _REMOTE_URL:
        data = _fetch_remote(_REMOTE_URL)

    if data is None:
        try:
            data = _load_local()
        except FileNotFoundError:
            data = {"version": "empty", "source": "fallback-empty", "categories": {}, "excluded_keywords": []}

    # Flatten brands for quick consumption
    flat: list[str] = []
    for cat in data.get("categories", {}).values():
        flat.extend(cat.get("brands", []))
    data["brands"] = sorted(set(b.lower() for b in flat))
    data["fetched_at"] = now

    _cache["data"] = data
    _cache["ts"] = now
    _cache["source"] = data.get("source", "unknown")
    return data
