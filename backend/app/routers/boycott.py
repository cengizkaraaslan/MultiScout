import json
from pathlib import Path
from fastapi import APIRouter, Body, Header, HTTPException, Query
from app.services.boycott_source import get_boycott_data
from app.services.admin_settings import verify_admin

router = APIRouter()

_LOCAL_PATH = Path(__file__).parent.parent.parent / "data" / "boycott_brands.json"


@router.get("/boycott-brands")
def get_boycott_brands(refresh: bool = Query(False)):
    data = get_boycott_data(force_refresh=refresh)
    return {
        "status": "success",
        "version": data.get("version"),
        "source": data.get("source"),
        "fetched_at": data.get("fetched_at"),
        "brands": data.get("brands", []),
        "categories": data.get("categories", {}),
        "excluded_keywords": data.get("excluded_keywords", []),
    }


def _require_admin(pw: str | None):
    if not verify_admin(pw):
        raise HTTPException(status_code=401, detail="Geçersiz admin şifresi")


@router.get("/admin/boycott-raw")
def admin_get_boycott(x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD")):
    _require_admin(x_admin_password)
    with open(_LOCAL_PATH, "r", encoding="utf-8") as f:
        return {"status": "success", "data": json.load(f)}


@router.put("/admin/boycott-raw")
def admin_put_boycott(payload: dict = Body(...), x_admin_password: str | None = Header(default=None, alias="X-ADMIN-PASSWORD")):
    _require_admin(x_admin_password)
    if not isinstance(payload, dict) or "categories" not in payload:
        raise HTTPException(status_code=400, detail="categories alanı zorunlu")
    _LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOCAL_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    # Reload cache
    get_boycott_data(force_refresh=True)
    return {"status": "success"}
