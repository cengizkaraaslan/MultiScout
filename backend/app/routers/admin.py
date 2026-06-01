from fastapi import APIRouter, Header, HTTPException, Body, UploadFile, File, Query
from fastapi.responses import Response
from app.services.admin_settings import (
    load_settings, save_settings, update_section, verify_admin, enabled_stores,
)
from app.services.auto_share import test_telegram, test_facebook, test_instagram, share_after_scrape

router = APIRouter()


def _require_admin(x_admin_password: str | None):
    if not verify_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="Geçersiz admin şifresi")


@router.post("/admin/login")
def admin_login(password: str = Body(..., embed=True)):
    if not verify_admin(password):
        raise HTTPException(status_code=401, detail="Geçersiz şifre")
    return {"status": "success", "message": "Giriş başarılı"}


@router.get("/admin/settings")
def get_settings(x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD")):
    _require_admin(x_admin_password)
    return {"status": "success", "data": load_settings()}


@router.put("/admin/settings")
def put_settings(payload: dict = Body(...), x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD")):
    _require_admin(x_admin_password)
    save_settings(payload)
    return {"status": "success", "data": load_settings()}


@router.patch("/admin/settings/{section}")
def patch_section(section: str, payload: dict = Body(...), x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD")):
    _require_admin(x_admin_password)
    updated = update_section(section, payload)
    return {"status": "success", "data": updated}


# Public endpoints (no auth needed) — frontend filtering
@router.post("/admin/test-telegram")
def admin_test_telegram(x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD")):
    _require_admin(x_admin_password)
    return test_telegram()


@router.post("/admin/test-facebook")
def admin_test_facebook(x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD")):
    _require_admin(x_admin_password)
    return test_facebook()


@router.post("/admin/test-instagram")
def admin_test_instagram(x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD")):
    _require_admin(x_admin_password)
    return test_instagram()


@router.post("/admin/trigger-share")
def admin_trigger_share(x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD")):
    _require_admin(x_admin_password)
    count = share_after_scrape()
    return {"status": "success", "shared": count}


@router.get("/admin/stats")
def admin_stats(x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD")):
    _require_admin(x_admin_password)
    from app.models.database import SessionLocal, Deal
    from sqlalchemy import func
    db = SessionLocal()
    try:
        total = db.query(Deal).count()
        by_platform = dict(db.query(Deal.platform, func.count(Deal.id)).group_by(Deal.platform).all())
        by_category = dict(db.query(Deal.category, func.count(Deal.id)).group_by(Deal.category).order_by(func.count(Deal.id).desc()).limit(15).all())
        avg_discount = db.query(func.avg(Deal.discount_percentage)).scalar() or 0
        high_discount = db.query(Deal).filter(Deal.discount_percentage >= 50).count()
        top_deals = db.query(Deal).order_by(Deal.discount_percentage.desc()).limit(10).all()
        return {
            "status": "success",
            "data": {
                "total": total,
                "by_platform": by_platform,
                "by_category": by_category,
                "avg_discount": round(float(avg_discount), 1),
                "high_discount_count": high_discount,
                "top_deals": [{"title": d.title[:80], "platform": d.platform, "discount": d.discount_percentage, "price": d.price, "link": d.link} for d in top_deals],
            },
        }
    finally:
        db.close()


@router.get("/admin/health")
def admin_health(x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD")):
    """Sağlık raporu — DB, scheduler, Playwright, disk, memory, son tarama zamanı."""
    _require_admin(x_admin_password)
    from app.services.health import get_health_report
    return {"status": "success", "data": get_health_report()}


@router.post("/admin/test-webhook")
def admin_test_webhook(
    kind: str = Query(..., description="discord veya slack"),
    x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD"),
):
    """Discord/Slack webhook test mesajı gönder."""
    _require_admin(x_admin_password)
    from app.services.webhooks import test_webhook
    return test_webhook(kind)


@router.get("/admin/backup")
def admin_backup(x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD")):
    """Settings + boycott zip backup — browser indirsin."""
    _require_admin(x_admin_password)
    from app.services.backup import create_backup
    blob, fname = create_backup()
    return Response(
        content=blob,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.post("/admin/restore")
async def admin_restore(
    file: UploadFile = File(...),
    restore_settings: bool = Query(True),
    restore_boycott: bool = Query(True),
    x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD"),
):
    """Yüklenen backup ZIP'den settings ve/veya boycott geri yükle."""
    _require_admin(x_admin_password)
    from app.services.backup import restore_backup
    data = await file.read()
    return restore_backup(data, restore_settings=restore_settings, restore_boycott=restore_boycott)


@router.post("/admin/scheduler/restart")
def admin_scheduler_restart(x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD")):
    """Scheduler'ı durdur + güncel settings ile yeniden başlat (tier config değişikliği sonrası)."""
    _require_admin(x_admin_password)
    from app.services.scheduler import restart_scheduler
    restart_scheduler()
    return {"status": "success", "message": "Scheduler yeniden başlatıldı"}


@router.get("/admin/logs")
def admin_logs(
    lines: int = 200,
    platform: str | None = None,
    level: str | None = None,
    search: str | None = None,
    source: str = "memory",
    file: str = "backend.log",
    x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD"),
):
    """Backend log akışı.

    source=memory (default): in-memory ring buffer (son 2000 satır, restart'ta uçar).
      - level: ERROR / WARN / INFO (ERROR sadece error, WARN error+warn, INFO hepsi)
      - search: substring filter
      - platform: [Vodafone] gibi tag filter

    source=disk: data/logs/<file> dosyasının son N satırı (restart-persistent).
      - file: backend.log / errors.log / scrape.log
    """
    _require_admin(x_admin_password)
    n = min(max(lines, 10), 2000)
    if source == "disk":
        from app.core.logging_config import tail_log_file, list_log_files
        raw = tail_log_file(file, n=n)
        rows = [{"msg": ln, "src": "disk"} for ln in raw]
        if level and level.upper() in ("ERROR", "WARN"):
            needle = "[ERROR]" if level.upper() == "ERROR" else None
            if needle:
                rows = [r for r in rows if needle in r["msg"]]
            else:
                rows = [r for r in rows if "[ERROR]" in r["msg"] or "[WARN" in r["msg"]]
        if search:
            sq = search.lower()
            rows = [r for r in rows if sq in r["msg"].lower()]
        return {
            "status": "success",
            "data": {"lines": rows, "count": len(rows), "files": list_log_files()},
        }
    from app.services.log_buffer import get_log_lines
    rows = get_log_lines(
        limit=n,
        platform_filter=platform,
        level_filter=level,
        search=search,
    )
    return {"status": "success", "data": {"lines": rows, "count": len(rows)}}


@router.get("/stores-status")
def public_stores_status():
    s = load_settings()
    return {
        "status": "success",
        "stores": s.get("stores", {}),
        "enabled": enabled_stores(),
        "theme": s.get("theme", {}),
        "maintenance": s.get("maintenance", {}),
    }
