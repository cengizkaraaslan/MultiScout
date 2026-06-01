"""Settings + boycott backup ZIP.

DB backup yapmaz (PostgreSQL dump tool container'da yok). Sadece config
katmanını yedekler — admin paneli yeniden kurulumda kolay restore için.
"""
from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path

from app.services.admin_settings import _PATH as SETTINGS_PATH, load_settings, save_settings

_BOYCOTT_PATH = Path(__file__).parent.parent.parent / "data" / "boycott_brands.json"


def create_backup() -> tuple[bytes, str]:
    """Settings + boycott + meta'yı zip'le. (zip bytes, dosya adı) döner."""
    buf = io.BytesIO()
    settings = load_settings()
    meta = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "version": "1",
        "source": "multiscout-admin-backup",
        "files": [],
    }
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Settings (canonical, en güncel)
        zf.writestr("admin_settings.json", json.dumps(settings, ensure_ascii=False, indent=2))
        meta["files"].append("admin_settings.json")
        # Boycott (varsa)
        if _BOYCOTT_PATH.exists():
            try:
                zf.write(_BOYCOTT_PATH, "boycott_brands.json")
                meta["files"].append("boycott_brands.json")
            except Exception:
                pass
        # Meta
        zf.writestr("meta.json", json.dumps(meta, indent=2))
    buf.seek(0)
    fname = f"multiscout-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.zip"
    return buf.getvalue(), fname


def restore_backup(zip_bytes: bytes, restore_settings: bool = True, restore_boycott: bool = True) -> dict:
    """Yüklenen ZIP'i çöz, settings ve/veya boycott'u geri yükle."""
    try:
        buf = io.BytesIO(zip_bytes)
        result = {"restored": [], "skipped": [], "errors": []}
        with zipfile.ZipFile(buf, "r") as zf:
            names = set(zf.namelist())
            if restore_settings and "admin_settings.json" in names:
                try:
                    raw = zf.read("admin_settings.json").decode("utf-8")
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        raise ValueError("Settings JSON dict olmalı")
                    save_settings(data)
                    result["restored"].append("admin_settings.json")
                except Exception as e:
                    result["errors"].append(f"settings: {e}")
            else:
                result["skipped"].append("admin_settings.json")
            if restore_boycott and "boycott_brands.json" in names:
                try:
                    _BOYCOTT_PATH.parent.mkdir(parents=True, exist_ok=True)
                    with open(_BOYCOTT_PATH, "wb") as f:
                        f.write(zf.read("boycott_brands.json"))
                    result["restored"].append("boycott_brands.json")
                except Exception as e:
                    result["errors"].append(f"boycott: {e}")
            else:
                result["skipped"].append("boycott_brands.json")
        return {"status": "success" if result["restored"] else "error", **result}
    except zipfile.BadZipFile:
        return {"status": "error", "error": "Geçersiz ZIP dosyası"}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}
