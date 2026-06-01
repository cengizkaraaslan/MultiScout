"""Outgoing webhook gönderici — Discord ve Slack için.

Big-discount deal'lerde admin'in tanımladığı URL'lere POST atar.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Iterable

from app.services.admin_settings import load_settings


# Aynı link'i kısa süre içinde iki kez gönderme (10 dakikalık cooldown)
_RECENT_LOCK = threading.Lock()
_RECENT_SENT: dict[str, float] = {}
_COOLDOWN_SEC = 600


def _should_send(link: str) -> bool:
    now = time.time()
    with _RECENT_LOCK:
        # Temizle eski kayıtları
        stale = [k for k, t in _RECENT_SENT.items() if now - t > _COOLDOWN_SEC]
        for k in stale:
            _RECENT_SENT.pop(k, None)
        if link in _RECENT_SENT:
            return False
        _RECENT_SENT[link] = now
        return True


def _post_json(url: str, payload: dict, timeout: int = 8) -> bool:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        # Slack/Discord retry-after vs.
        print(f"[WEBHOOK] HTTP {e.code} → {url[:60]}", flush=True)
        return False
    except Exception as e:
        print(f"[WEBHOOK] err: {e}", flush=True)
        return False


def _format_discord(deal: dict) -> dict:
    title = (deal.get("title") or "")[:200]
    price = deal.get("price") or "?"
    discount = deal.get("discount_percentage") or 0
    platform = (deal.get("platform") or deal.get("source") or "").upper()
    link = deal.get("link") or ""
    image = deal.get("image") or ""
    return {
        "username": "MultiScout",
        "embeds": [{
            "title": title,
            "url": link,
            "color": 0xef4444 if discount >= 70 else 0xf97316 if discount >= 50 else 0x3b82f6,
            "fields": [
                {"name": "Fiyat", "value": str(price), "inline": True},
                {"name": "İndirim", "value": f"%{discount}", "inline": True},
                {"name": "Platform", "value": platform, "inline": True},
            ],
            "thumbnail": {"url": image} if image else None,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }],
    }


def _format_slack(deal: dict) -> dict:
    title = (deal.get("title") or "")[:200]
    price = deal.get("price") or "?"
    discount = deal.get("discount_percentage") or 0
    platform = (deal.get("platform") or deal.get("source") or "").upper()
    link = deal.get("link") or ""
    return {
        "text": f"*MultiScout* — *%{discount} indirim*",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"%{discount} indirim — {platform}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"<{link}|{title}>\n*Fiyat:* {price}"},
            },
        ],
    }


def send_deal_to_webhooks(deal: dict) -> int:
    """Verilen deal'i admin'in tanımladığı webhook'lara gönder.
    Dönüş: başarılı gönderim sayısı.

    Cooldown: aynı link 10 dk içinde tekrar gönderilmez.
    """
    if not deal or not deal.get("link"):
        return 0
    settings = load_settings()
    wh = settings.get("webhooks") or {}
    if not wh.get("enabled"):
        return 0
    min_discount = int(wh.get("min_discount") or 50)
    if int(deal.get("discount_percentage") or 0) < min_discount:
        return 0
    # Skip if recently sent
    if not _should_send(deal["link"]):
        return 0

    sent = 0
    discord_url = (wh.get("discord_url") or "").strip()
    if discord_url:
        if _post_json(discord_url, _format_discord(deal)):
            sent += 1
    slack_url = (wh.get("slack_url") or "").strip()
    if slack_url:
        if _post_json(slack_url, _format_slack(deal)):
            sent += 1
    return sent


def send_batch_to_webhooks(deals: Iterable[dict], cap: int = 5) -> int:
    """Birden fazla deal'i toplu gönder — günün top X fırsatı için.
    Cap: max gönderim sayısı (rate limit'ten korunmak için)."""
    sent_total = 0
    for d in list(deals)[:cap]:
        try:
            sent_total += send_deal_to_webhooks(d)
        except Exception:
            pass
    return sent_total


def test_webhook(kind: str) -> dict:
    """Admin'in panel üzerinden tetiklediği test gönderimi."""
    settings = load_settings()
    wh = settings.get("webhooks") or {}
    test_deal = {
        "title": "MultiScout test bildirimi — bu sadece bir test mesajıdır",
        "price": "0,00 TL",
        "discount_percentage": 99,
        "platform": "test",
        "link": "https://multiscout.app",
        "image": "",
    }
    if kind == "discord":
        url = (wh.get("discord_url") or "").strip()
        if not url:
            return {"status": "error", "message": "Discord webhook URL boş"}
        ok = _post_json(url, _format_discord(test_deal))
        return {"status": "success" if ok else "error", "message": "Discord test gönderildi" if ok else "Gönderilemedi"}
    if kind == "slack":
        url = (wh.get("slack_url") or "").strip()
        if not url:
            return {"status": "error", "message": "Slack webhook URL boş"}
        ok = _post_json(url, _format_slack(test_deal))
        return {"status": "success" if ok else "error", "message": "Slack test gönderildi" if ok else "Gönderilemedi"}
    return {"status": "error", "message": f"Bilinmeyen kanal: {kind}"}
