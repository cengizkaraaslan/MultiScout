"""Otomatik sosyal medya paylaşımı — Telegram + (gelecekte IG/FB)."""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.admin_settings import load_settings

_SHARED_LOG = Path(__file__).parent.parent.parent / "data" / "shared_deals.json"


def _load_shared() -> dict[str, Any]:
    if not _SHARED_LOG.exists():
        return {"links": [], "log": []}
    try:
        with open(_SHARED_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"links": [], "log": []}


def _save_shared(data: dict[str, Any]) -> None:
    _SHARED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_SHARED_LOG, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _today_count(log: list[dict]) -> int:
    today = datetime.utcnow().date().isoformat()
    return sum(1 for entry in log if entry.get("date", "").startswith(today))


def _post_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    if not bot_token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        body = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "false",
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[AUTO_SHARE] Telegram error: {e}", flush=True)
        return False


def _post_facebook_page(page_id: str, page_access_token: str, message: str, link: str = "") -> bool:
    if not page_id or not page_access_token:
        return False
    try:
        url = f"https://graph.facebook.com/v18.0/{page_id}/feed"
        params = {"message": message, "access_token": page_access_token}
        if link:
            params["link"] = link
        body = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        print(f"[AUTO_SHARE] Facebook error: {e}", flush=True)
        return False


def _post_instagram(business_account_id: str, access_token: str, image_url: str, caption: str) -> bool:
    """Instagram Graph API: 2-step — create media container, then publish."""
    if not business_account_id or not access_token or not image_url:
        return False
    try:
        # Step 1: create media container
        create_url = f"https://graph.facebook.com/v18.0/{business_account_id}/media"
        create_body = urllib.parse.urlencode({
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token,
        }).encode("utf-8")
        req = urllib.request.Request(create_url, data=create_body, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode("utf-8"))
            creation_id = data.get("id")
        if not creation_id:
            return False
        # Step 2: publish
        publish_url = f"https://graph.facebook.com/v18.0/{business_account_id}/media_publish"
        publish_body = urllib.parse.urlencode({
            "creation_id": creation_id,
            "access_token": access_token,
        }).encode("utf-8")
        req = urllib.request.Request(publish_url, data=publish_body, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[AUTO_SHARE] Instagram error: {e}", flush=True)
        return False


def _format_deal_text(deal: dict[str, Any]) -> str:
    """HTML format (Telegram için)."""
    title = (deal.get("title") or "").strip()
    price = (deal.get("price") or "").strip()
    discount = int(deal.get("discount_percentage") or 0)
    platform = (deal.get("platform") or "").capitalize()
    link = deal.get("link") or ""
    badge = "🔥" if discount >= 70 else "💸"
    return (
        f"{badge} <b>%{discount} İNDİRİM</b>\n"
        f"\n"
        f"<b>{title[:150]}</b>\n"
        f"💰 {price}\n"
        f"🏪 {platform}\n"
        f"\n"
        f"{link}"
    )


def _format_deal_text_plain(deal: dict[str, Any]) -> str:
    """Plain text (Facebook/Instagram için)."""
    title = (deal.get("title") or "").strip()
    price = (deal.get("price") or "").strip()
    discount = int(deal.get("discount_percentage") or 0)
    platform = (deal.get("platform") or "").capitalize()
    badge = "🔥" if discount >= 70 else "💸"
    return (
        f"{badge} %{discount} İNDİRİM\n\n"
        f"{title[:200]}\n\n"
        f"💰 {price}\n"
        f"🏪 {platform}\n\n"
        f"#firsat #indirim #{platform.lower()}"
    )


def share_new_deals(deals: list[dict[str, Any]]) -> int:
    """Paylaşılmamış yüksek indirim deal'leri paylaş. Returns shared count."""
    settings = load_settings()
    auto = settings.get("auto_share", {})
    if not auto.get("enabled"):
        return 0

    min_discount = int(auto.get("min_discount", 50))
    max_per_day = int(auto.get("max_per_day", 10))
    platforms = auto.get("platforms", ["telegram"])

    shared = _load_shared()
    seen_links = set(shared.get("links", []))
    today_count = _today_count(shared.get("log", []))
    slots_left = max(0, max_per_day - today_count)
    if slots_left <= 0:
        return 0

    social = settings.get("social", {})
    telegram_cfg = social.get("telegram", {}) if "telegram" in platforms else None
    facebook_cfg = social.get("facebook", {}) if "facebook" in platforms else None
    instagram_cfg = social.get("instagram", {}) if "instagram" in platforms else None

    candidates = []
    for d in deals:
        link = d.get("link") or ""
        if not link or link in seen_links:
            continue
        discount = int(d.get("discount_percentage") or 0)
        if discount < min_discount:
            continue
        candidates.append(d)

    candidates.sort(key=lambda d: int(d.get("discount_percentage") or 0), reverse=True)
    to_share = candidates[:slots_left]

    sent = 0
    for d in to_share:
        success = False
        text = _format_deal_text(d)
        plain_text = _format_deal_text_plain(d)
        if telegram_cfg and telegram_cfg.get("enabled"):
            ok = _post_telegram(telegram_cfg.get("bot_token", ""), telegram_cfg.get("chat_id", ""), text)
            if ok:
                success = True
        if facebook_cfg and facebook_cfg.get("enabled"):
            ok = _post_facebook_page(
                facebook_cfg.get("page_id", ""),
                facebook_cfg.get("page_access_token", ""),
                plain_text,
                d.get("link") or "",
            )
            if ok:
                success = True
        if instagram_cfg and instagram_cfg.get("enabled") and d.get("image"):
            ok = _post_instagram(
                instagram_cfg.get("business_account_id", ""),
                instagram_cfg.get("access_token", ""),
                d.get("image"),
                plain_text,
            )
            if ok:
                success = True

        if success:
            seen_links.add(d["link"])
            shared.setdefault("log", []).append({
                "date": datetime.utcnow().isoformat(),
                "link": d["link"],
                "title": (d.get("title") or "")[:100],
                "discount": int(d.get("discount_percentage") or 0),
                "platforms": [p for p in platforms if social.get(p, {}).get("enabled")],
            })
            sent += 1

    shared["links"] = list(seen_links)
    _save_shared(shared)
    if sent:
        print(f"[AUTO_SHARE] {sent} deal sosyal medyaya paylaşıldı", flush=True)
    return sent


def share_after_scrape() -> int:
    """Tarama sonrası DB'den en yeni yüksek indirim deal'leri çek ve paylaş."""
    from app.models.database import Deal, SessionLocal

    settings = load_settings()
    auto = settings.get("auto_share", {})
    if not auto.get("enabled"):
        return 0
    min_discount = int(auto.get("min_discount", 50))

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=2)
        rows = (
            db.query(Deal)
            .filter(Deal.discount_percentage >= min_discount)
            .filter(Deal.last_updated >= cutoff)
            .order_by(Deal.discount_percentage.desc())
            .limit(50)
            .all()
        )
        deals = [{
            "title": r.title,
            "price": r.price,
            "discount_percentage": r.discount_percentage,
            "link": r.link,
            "platform": r.platform,
        } for r in rows]
    finally:
        db.close()

    return share_new_deals(deals)


def test_telegram() -> dict[str, Any]:
    """Admin'den manuel test mesajı yolla."""
    settings = load_settings()
    tg = settings.get("social", {}).get("telegram", {})
    if not tg.get("bot_token") or not tg.get("chat_id"):
        return {"ok": False, "error": "Bot token veya chat ID eksik"}
    text = "🧪 <b>MultiScout test mesajı</b>\n\nOtomatik paylaşım çalışıyor."
    ok = _post_telegram(tg["bot_token"], tg["chat_id"], text)
    return {"ok": ok, "error": "" if ok else "Telegram API hata döndü (token/chat_id kontrol et)"}


def test_facebook() -> dict[str, Any]:
    settings = load_settings()
    fb = settings.get("social", {}).get("facebook", {})
    if not fb.get("page_id") or not fb.get("page_access_token"):
        return {"ok": False, "error": "Page ID veya access token eksik"}
    msg = "🧪 MultiScout test gönderisi — otomatik paylaşım çalışıyor."
    ok = _post_facebook_page(fb["page_id"], fb["page_access_token"], msg)
    return {"ok": ok, "error": "" if ok else "Facebook Graph API hatası — token/page_id kontrol et"}


def test_instagram() -> dict[str, Any]:
    settings = load_settings()
    ig = settings.get("social", {}).get("instagram", {})
    if not ig.get("business_account_id") or not ig.get("access_token"):
        return {"ok": False, "error": "Business Account ID veya access token eksik"}
    # IG için bir image_url gerekli — test placeholder
    test_image = "https://via.placeholder.com/1080x1080.png?text=MultiScout+Test"
    caption = "🧪 MultiScout test paylaşımı"
    ok = _post_instagram(ig["business_account_id"], ig["access_token"], test_image, caption)
    return {"ok": ok, "error": "" if ok else "Instagram Graph API hatası (image_url, token, account_id kontrol et)"}
