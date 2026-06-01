"""Multi-tier scheduler — kategori bazlı interval.

Admin paneli `scheduler.tiers` config'inden okur:
  - market: 30 dk (taze gıda fiyatları)
  - fashion: 90 dk (orta tempo)
  - marketplace: 60 dk (büyük platformlar)
  - electronics: 4 saat (yavaş değişim)
  - home: 3 saat
  - default: 2 saat (kapsanmayan platformlar)

Her tier kendi job'una sahip. Tier'ın min_discount değeri scrape sırasında uygulanır.

ENV `SCHEDULER_ENABLED=false` ile tamamen kapatılabilir.
"""
from __future__ import annotations

import asyncio
import os
import threading
from datetime import datetime
from typing import Iterable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

scheduler = BackgroundScheduler()

CLEANUP_INTERVAL_HOUR = int(os.getenv("CLEANUP_INTERVAL_HOUR", "3"))
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() not in ("0", "false", "no")

# Aynı tier'ın iki kez paralel çalışmasını engelle
_TIER_LOCKS: dict[str, threading.Lock] = {}


def _lock_for(tier: str) -> threading.Lock:
    if tier not in _TIER_LOCKS:
        _TIER_LOCKS[tier] = threading.Lock()
    return _TIER_LOCKS[tier]


def _try_auto_share() -> None:
    try:
        from app.services.auto_share import share_after_scrape
        share_after_scrape()
    except Exception as e:
        print(f"[SCHEDULER] auto-share error: {e}", flush=True)


def _try_webhook_top_deals() -> None:
    """Tarama sonrası eşik üstü deal'leri webhook'lara gönder."""
    try:
        from app.services.webhooks import send_batch_to_webhooks
        from app.services.admin_settings import load_settings
        from app.models.database import SessionLocal, Deal
        wh = (load_settings().get("webhooks") or {})
        if not wh.get("enabled"):
            return
        threshold = int(wh.get("min_discount") or 50)
        db = SessionLocal()
        try:
            # Son 1 saatte eklenen + threshold üstü deal'ler
            from datetime import datetime, timedelta
            cutoff = datetime.utcnow() - timedelta(hours=1)
            rows = (
                db.query(Deal)
                .filter(Deal.discount_percentage >= threshold)
                .filter(Deal.last_updated >= cutoff)
                .order_by(Deal.discount_percentage.desc())
                .limit(10)
                .all()
            )
            payloads = [
                {
                    "title": r.title,
                    "price": r.price,
                    "discount_percentage": r.discount_percentage,
                    "platform": r.platform,
                    "link": r.link,
                    "image": r.image,
                }
                for r in rows
            ]
        finally:
            db.close()
        sent = send_batch_to_webhooks(payloads, cap=5)
        if sent:
            print(f"[SCHEDULER] webhook: {sent} mesaj gönderildi", flush=True)
    except Exception as e:
        print(f"[SCHEDULER] webhook error: {e}", flush=True)


async def _run_platforms(platforms: list[str], min_discount: int) -> None:
    """Verilen platformları paralel tara."""
    from app.routers.scrape import run_scrape_all_job
    if not platforms:
        return
    await asyncio.gather(
        *[run_scrape_all_job(min_discount=min_discount, platform=p) for p in platforms],
        return_exceptions=True,
    )


def _get_tier_platforms(tier_name: str, tier_cfg: dict, all_active: set[str], covered: set[str]) -> list[str]:
    """Tier'ın kapsadığı, AKTİF olan platformları döner. 'default' tier kapsanmayanları alır."""
    cfg_platforms = [p for p in (tier_cfg.get("platforms") or []) if isinstance(p, str)]
    if tier_name == "default":
        platforms = [p for p in all_active if p not in covered]
    else:
        platforms = [p for p in cfg_platforms if p in all_active]
    return platforms


def _make_tier_runner(tier_name: str):
    """Tier-specific runner. Settings runtime'da değişirse her job çağrısında okur."""
    def _runner():
        lock = _lock_for(tier_name)
        if not lock.acquire(blocking=False):
            print(f"[SCHEDULER] {tier_name} already running, skipping", flush=True)
            return
        try:
            from app.services.admin_settings import load_settings, enabled_stores
            settings = load_settings()
            scheduler_cfg = settings.get("scheduler") or {}
            if not scheduler_cfg.get("enabled", True):
                print(f"[SCHEDULER] {tier_name} skipped — scheduler disabled in settings", flush=True)
                return
            tiers_cfg = scheduler_cfg.get("tiers") or {}
            tier_cfg = tiers_cfg.get(tier_name) or {}
            if not tier_cfg.get("enabled", True):
                print(f"[SCHEDULER] {tier_name} skipped — tier disabled in settings", flush=True)
                return
            all_active = set(enabled_stores())
            # Hangi platformlar hangi tier'a — covered set'ini hesapla
            covered: set[str] = set()
            for other_name, other_cfg in tiers_cfg.items():
                if other_name == "default":
                    continue
                covered.update(other_cfg.get("platforms") or [])
            platforms = _get_tier_platforms(tier_name, tier_cfg, all_active, covered)
            if not platforms:
                print(f"[SCHEDULER] {tier_name}: no active platforms, skipping", flush=True)
                return
            min_discount = int(tier_cfg.get("min_discount") or 5)
            print(
                f"[SCHEDULER] {tier_name} started ({len(platforms)} platforms, min_discount={min_discount}) @ {datetime.now()}",
                flush=True,
            )
            asyncio.run(_run_platforms(platforms, min_discount))
            print(f"[SCHEDULER] {tier_name} completed @ {datetime.now()}", flush=True)
            _try_auto_share()
            _try_webhook_top_deals()
        except Exception as e:
            print(f"[SCHEDULER] {tier_name} job error: {e}", flush=True)
        finally:
            lock.release()

    _runner.__name__ = f"run_tier_{tier_name}"
    return _runner


def run_cleanup_duplicates() -> None:
    from app.models.database import cleanup_duplicates, SessionLocal
    db = SessionLocal()
    try:
        print(f"[SCHEDULER] Cleanup duplicates started @ {datetime.now()}", flush=True)
        cleanup_duplicates(db)
        print(f"[SCHEDULER] Cleanup duplicates completed @ {datetime.now()}", flush=True)
    except Exception as e:
        print(f"[SCHEDULER] Cleanup duplicates error: {e}", flush=True)
    finally:
        db.close()


def _iter_tier_names() -> Iterable[str]:
    """Yapılandırma sırasını koruyarak tier isimlerini döner."""
    from app.services.admin_settings import load_settings
    tiers = (load_settings().get("scheduler") or {}).get("tiers") or {}
    return list(tiers.keys())


def start_scheduler() -> None:
    if not SCHEDULER_ENABLED:
        print("[SCHEDULER] Disabled via SCHEDULER_ENABLED=false", flush=True)
        return
    if scheduler.running:
        return

    from app.services.admin_settings import load_settings
    sched_cfg = (load_settings().get("scheduler") or {})
    tiers_cfg = sched_cfg.get("tiers") or {}

    job_count = 0
    for tier_name, tier_cfg in tiers_cfg.items():
        if not isinstance(tier_cfg, dict):
            continue
        interval_min = max(int(tier_cfg.get("interval_min") or 60), 5)
        runner = _make_tier_runner(tier_name)
        scheduler.add_job(
            runner,
            trigger=IntervalTrigger(minutes=interval_min),
            id=f"tier_{tier_name}",
            name=f"Tier {tier_name} ({interval_min} min)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        job_count += 1
        print(f"[SCHEDULER] tier '{tier_name}' → {interval_min} min", flush=True)

    scheduler.add_job(
        run_cleanup_duplicates,
        trigger=IntervalTrigger(hours=CLEANUP_INTERVAL_HOUR),
        id="cleanup_duplicates",
        name=f"Cleanup Duplicates ({CLEANUP_INTERVAL_HOUR} hours)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    print(f"[SCHEDULER] Started with {job_count} tier(s) + cleanup", flush=True)


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown()
        print("[SCHEDULER] stopped", flush=True)


def restart_scheduler() -> None:
    """Admin panelinden config değişikliği sonrası çağrılır."""
    stop_scheduler()
    start_scheduler()
