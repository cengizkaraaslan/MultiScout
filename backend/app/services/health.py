"""Backend sağlık check'leri — DB, scheduler, Playwright, disk, memory."""
from __future__ import annotations

import os
import shutil
import time
from datetime import datetime, timezone

_START_TS = time.time()


def _check_db() -> dict:
    try:
        from app.models.database import SessionLocal, Deal
        from sqlalchemy import func
        db = SessionLocal()
        try:
            count = db.query(func.count(Deal.id)).scalar() or 0
            return {"ok": True, "deal_count": int(count)}
        finally:
            db.close()
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _check_scheduler() -> dict:
    try:
        from app.services.scheduler import scheduler as sched
        if not sched.running:
            return {"ok": False, "running": False, "jobs": []}
        jobs = []
        for j in sched.get_jobs():
            nxt = getattr(j, "next_run_time", None)
            jobs.append({
                "id": j.id,
                "name": j.name,
                "next_run": nxt.isoformat() if nxt else None,
            })
        return {"ok": True, "running": True, "jobs": jobs}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _check_playwright() -> dict:
    try:
        # Sadece import çalışıyor mu kontrolü (browser launch çok pahalı)
        from playwright.async_api import async_playwright  # noqa: F401
        import playwright
        ver = getattr(playwright, "__version__", "?")
        return {"ok": True, "version": ver}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _check_disk(path: str = "/app") -> dict:
    try:
        total, used, free = shutil.disk_usage(path)
        pct_free = round((free / total) * 100, 1)
        return {
            "ok": pct_free > 5,
            "free_gb": round(free / (1024 ** 3), 2),
            "total_gb": round(total / (1024 ** 3), 2),
            "pct_free": pct_free,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _check_memory() -> dict:
    try:
        # /proc/meminfo Linux container — Docker'da çalışır
        with open("/proc/meminfo", "r") as f:
            info = {}
            for line in f:
                k, _, v = line.partition(":")
                info[k.strip()] = v.strip()
        total_kb = int(info.get("MemTotal", "0 kB").split()[0])
        avail_kb = int(info.get("MemAvailable", "0 kB").split()[0])
        pct_free = round((avail_kb / total_kb) * 100, 1) if total_kb else 0
        return {
            "ok": pct_free > 5,
            "free_mb": round(avail_kb / 1024, 1),
            "total_mb": round(total_kb / 1024, 1),
            "pct_free": pct_free,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _check_last_scrapes() -> dict:
    """SCRAPE_ALL_STATUS dict'inden her platformun son güncelleme zamanı."""
    try:
        from app.routers.scrape import SCRAPE_ALL_STATUS
        per = {}
        for plat, st in SCRAPE_ALL_STATUS.items():
            per[plat] = {
                "status": st.get("status"),
                "updated_at": st.get("updated_at"),
            }
        return {"ok": True, "platforms": per}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def get_health_report() -> dict:
    """Tüm sağlık check'lerini topla. Status:
    - ok: hepsi yeşil
    - warning: bir veya daha fazla problem (disk/memory düşük)
    - critical: db veya playwright down
    """
    checks = {
        "db": _check_db(),
        "scheduler": _check_scheduler(),
        "playwright": _check_playwright(),
        "disk": _check_disk(),
        "memory": _check_memory(),
        "scrapes": _check_last_scrapes(),
    }
    critical = not checks["db"]["ok"] or not checks["playwright"]["ok"]
    warnings = (
        not checks["disk"].get("ok", True)
        or not checks["memory"].get("ok", True)
        or not checks["scheduler"].get("ok", True)
    )
    status = "critical" if critical else "warning" if warnings else "ok"
    return {
        "status": status,
        "uptime_sec": int(time.time() - _START_TS),
        "now": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "env": {
            "python": os.getenv("PYTHON_VERSION", ""),
            "scheduler_enabled": os.getenv("SCHEDULER_ENABLED", "true"),
            "data_dir": os.getenv("DATA_DIR", "data"),
        },
    }
