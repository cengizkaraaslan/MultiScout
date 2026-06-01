import logging
import os
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.logging_config import install_disk_logging
from app.models.database import init_db
from app.routers import deals, scrape, compare, boycott, admin, ai
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.log_buffer import install_log_capture

# Disk logging önce — log_buffer Tee'si dış dünyaya yazarken disk handler'larını da
# kullansın diye. install_log_capture print'leri yakalar; install_disk_logging
# RotatingFileHandler'ları root logger'a takar.
install_disk_logging()
install_log_capture()

_LOG = logging.getLogger("multiscout.app")

# /api/scrape-all-status polling gürültüsünü uvicorn access loglarından sustur
class _SuppressStatusPoll(logging.Filter):
    _TARGETS = ("/api/scrape-all-status", "/api/admin/logs")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(t in msg for t in self._TARGETS)


logging.getLogger("uvicorn.access").addFilter(_SuppressStatusPoll())

app = FastAPI(title="MultiScout API")


@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    """500'leri stack trace ile errors.log'a yaz, kullanıcıya kısa mesaj döner."""
    tb = traceback.format_exc()
    _LOG.error(
        "Unhandled exception on %s %s :: %s\n%s",
        request.method, request.url.path, exc, tb,
    )
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": f"Sunucu hatası: {type(exc).__name__}"},
    )

_cors_env = os.getenv("CORS_ORIGINS", "http://localhost:3000")
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()
    start_scheduler()

@app.on_event("shutdown")
def shutdown():
    stop_scheduler()

app.include_router(deals.router, prefix="/api")
app.include_router(scrape.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(boycott.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(ai.router, prefix="/api")

@app.get("/")
def health_check():
    return {"status": "ok", "message": "MultiScout API çalışıyor!"}
