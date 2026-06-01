"""AI özet — Claude API ile fırsat analizi."""
import json
import os
import time
from pathlib import Path
from typing import Any

_CACHE_PATH = Path(__file__).parent.parent.parent / "data" / "ai_summary_cache.json"
_CACHE_TTL = int(os.getenv("AI_SUMMARY_CACHE_TTL", "86400"))  # 24h

_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
_MODEL = os.getenv("AI_SUMMARY_MODEL", "claude-haiku-4-5-20251001")

_cache: dict[str, Any] | None = None


def _load_cache() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    if not _CACHE_PATH.exists():
        _cache = {}
        return _cache
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
        return _cache
    except (json.JSONDecodeError, OSError):
        _cache = {}
        return _cache


def _save_cache():
    global _cache
    if _cache is None:
        return
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def get_cached(link: str) -> str | None:
    cache = _load_cache()
    entry = cache.get(link)
    if not entry:
        return None
    if (time.time() - entry.get("ts", 0)) > _CACHE_TTL:
        return None
    return entry.get("summary")


def set_cached(link: str, summary: str):
    cache = _load_cache()
    cache[link] = {"ts": time.time(), "summary": summary}
    _save_cache()


def is_available() -> bool:
    return bool(_API_KEY)


def summarize(deal: dict[str, Any]) -> dict[str, Any]:
    """Tek bir ürün için Claude API ile fırsat analizi yap."""
    link = deal.get("link", "")
    cached = get_cached(link)
    if cached:
        return {"ok": True, "summary": cached, "cached": True}

    if not _API_KEY:
        return {"ok": False, "error": "ANTHROPIC_API_KEY env tanımlı değil"}

    try:
        import anthropic
    except ImportError:
        return {"ok": False, "error": "anthropic paketi yüklü değil"}

    title = (deal.get("title") or "").strip()
    price = (deal.get("price") or "").strip()
    discount = int(deal.get("discount_percentage") or 0)
    platform = deal.get("platform") or ""
    history = deal.get("price_history") or []

    history_str = ""
    if len(history) > 1:
        for h in history[-5:]:
            history_str += f"  - {h.get('date', '')[:10]}: {h.get('price', '')}\n"

    prompt = (
        f"Bu Türkiye e-ticaret sitesindeki bir fırsat ürünü. Çok kısa (2-3 cümle, max 40 kelime) "
        f"Türkçe analiz yap: bu fiyat gerçekten iyi mi, almaya değer mi, veya beklemeli mi? "
        f"İndirim oranı ve fiyat geçmişine göre yorum yap. Pazarlama dili kullanma, dürüst ve net konuş.\n\n"
        f"Ürün: {title}\n"
        f"Fiyat: {price}\n"
        f"İndirim: %{discount}\n"
        f"Platform: {platform}\n"
    )
    if history_str:
        prompt += f"\nFiyat geçmişi:\n{history_str}"

    try:
        client = anthropic.Anthropic(api_key=_API_KEY)
        message = client.messages.create(
            model=_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        summary = ""
        for block in message.content:
            if getattr(block, "type", "") == "text":
                summary += block.text
        summary = summary.strip()
        if summary:
            set_cached(link, summary)
            return {"ok": True, "summary": summary, "cached": False}
        return {"ok": False, "error": "Claude boş yanıt döndü"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
