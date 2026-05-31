"""Admin settings: stores enable/disable, theme, social media config."""
import json
import os
import threading
from pathlib import Path
from typing import Any

_PATH = Path(__file__).parent.parent.parent / "data" / "admin_settings.json"
_LOCK = threading.Lock()

DEFAULTS: dict[str, Any] = {
    "stores": {
        "amazon": True, "trendyol": True, "n11": True, "hepsiburada": True,
        "pazarama": True, "ciceksepeti": True, "vatan": True, "teknosa": True,
        "decathlon": False, "steam": True, "mediamarkt": True, "defacto": True,
        "gratis": True,
        "a101": True, "bim": True, "sok": True, "migros": True,
        "carrefoursa": True, "tarimkredi": True,
        "hakmarexpress": True, "macrocenter": True, "bizimtoptan": True,
        "peynircibaba": True,
        "burgerking": True,
        "lcwaikiki": True, "koton": True, "mavi": True,
        "boyner": True, "penti": True, "watsons": True, "dr": True,
        "karaca": True, "englishhome": False, "idefix": True, "tchibo": True,
        "mudo": True, "madamecoco": True, "vivense": True,
        "tepehome": True, "skechers": True,
        "toyzz": True, "yargici": True, "kitapyurdu": True,
        "pttavm": True, "sportive": True, "newbalance": True,
        "flo": True, "hummel": True, "evidea": True,
        "beko": True, "arcelik": True, "vestel": True,
        "network": True, "northface": True,
        "mac": True, "apple": True,
        "saatvesaat": True, "altinbas": True, "pasabahce": True,
        "akakce": True, "ramsey": True, "atasay": True,
        "reebok": True, "sarar": True, "huawei": True, "lego": True,
        "casper": True, "monster": False,
    },
    "theme": {
        "primary": "#f97316",
        "accent": "#ef4444",
        "logo_text": "MultiScout",
        "tagline": "Akıllı Fırsat Takipçisi",
    },
    "social": {
        "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
        "instagram": {"enabled": False, "access_token": "", "business_account_id": ""},
        "facebook": {"enabled": False, "page_access_token": "", "page_id": ""},
    },
    "auto_share": {
        "enabled": False,
        "min_discount": 50,
        "max_per_day": 10,
        "platforms": ["telegram"],
    },
    "scheduler": {
        "enabled": True,
        # Eski (geriye uyumluluk için bırakıldı, kullanılmıyorsa zarar yok)
        "amazon_interval_min": 60,
        "other_interval_min": 45,
        # Çok-katmanlı (multi-tier) interval — kategoriye göre farklı zamanlama
        # Her tier: { interval_min, min_discount, platforms[] }
        # Tier'larda olmayan platformlar "default" tier'ına düşer
        "tiers": {
            "market": {
                "enabled": True,
                "interval_min": 30,
                "min_discount": 0,
                "platforms": ["a101", "bim", "sok", "migros", "carrefoursa", "tarimkredi", "hakmarexpress", "macrocenter", "bizimtoptan", "peynircibaba", "tchibo"],
            },
            "campaigns": {
                "enabled": True,
                "interval_min": 360,
                "min_discount": 0,
                "platforms": ["burgerking"],
            },
            "fashion": {
                "enabled": True,
                "interval_min": 90,
                "min_discount": 10,
                "platforms": ["lcwaikiki", "koton", "mavi", "defacto", "boyner", "penti", "watsons", "mudo", "network", "yargici", "ramsey", "sarar", "reebok"],
            },
            "marketplace": {
                "enabled": True,
                "interval_min": 60,
                "min_discount": 15,
                "platforms": ["amazon", "trendyol", "n11", "hepsiburada", "pazarama", "ciceksepeti", "pttavm"],
            },
            "electronics": {
                "enabled": True,
                "interval_min": 240,
                "min_discount": 5,
                "platforms": ["vatan", "teknosa", "mediamarkt", "beko", "arcelik", "vestel", "apple", "huawei", "casper", "monster"],
            },
            "home": {
                "enabled": True,
                "interval_min": 180,
                "min_discount": 10,
                "platforms": ["karaca", "madamecoco", "vivense", "tepehome", "evidea", "englishhome", "pasabahce"],
            },
            "default": {
                "enabled": True,
                "interval_min": 120,
                "min_discount": 5,
                "platforms": [],  # kapsanmayan tüm aktif platformlar
            },
        },
    },
    "webhooks": {
        "enabled": False,
        "min_discount": 50,           # Bu yüzdenin üstündeki deal'ler gönderilir
        "discord_url": "",            # https://discord.com/api/webhooks/...
        "slack_url": "",              # https://hooks.slack.com/services/...
    },
    "maintenance": {
        "enabled": False,
        "message": "Şu an bakım modundayız, kısa süre sonra döneceğiz.",
    },
}


def _merge(base: dict, overrides: dict) -> dict:
    out = dict(base)
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings() -> dict[str, Any]:
    with _LOCK:
        if not _PATH.exists():
            save_settings_unlocked(DEFAULTS)
            return dict(DEFAULTS)
        try:
            with open(_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _merge(DEFAULTS, data) if isinstance(data, dict) else dict(DEFAULTS)
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULTS)


def save_settings_unlocked(settings: dict[str, Any]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def save_settings(settings: dict[str, Any]) -> None:
    with _LOCK:
        save_settings_unlocked(settings)


def update_section(section: str, payload: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    if section not in current:
        current[section] = {}
    current[section] = _merge(current[section] if isinstance(current[section], dict) else {}, payload)
    save_settings(current)
    return current


def is_store_enabled(platform: str) -> bool:
    settings = load_settings()
    stores = settings.get("stores", {})
    return bool(stores.get(platform.lower(), True))


def enabled_stores() -> list[str]:
    settings = load_settings()
    stores = settings.get("stores", {})
    return [k for k, v in stores.items() if v]


ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "123456")


def verify_admin(password: str | None) -> bool:
    if not password:
        return False
    return password == ADMIN_PASSWORD
