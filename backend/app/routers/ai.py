from fastapi import APIRouter, Body, HTTPException
from app.services.ai_summary import summarize, is_available

router = APIRouter()


@router.post("/ai-summary")
def ai_summary(payload: dict = Body(...)):
    if not is_available():
        raise HTTPException(status_code=503, detail="AI özet servisi etkin değil (ANTHROPIC_API_KEY eksik)")
    if not payload.get("link") or not payload.get("title"):
        raise HTTPException(status_code=400, detail="link ve title zorunlu")
    return summarize(payload)


@router.get("/ai-summary/status")
def ai_status():
    return {"status": "success", "available": is_available()}
