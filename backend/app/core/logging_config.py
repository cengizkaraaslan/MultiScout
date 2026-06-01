"""Disk-persistent rotating log setup.

backend.log: tüm INFO+ akış (rolling 10MB × 5 dosya = ~50MB cap)
errors.log:  sadece ERROR/CRITICAL — sorun avı için
scrape.log:  scraper'ların print'lerinden filter ile akan satırlar

install_disk_logging() main.py startup'ta çağrılır.
"""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent.parent / "data" / "logs"

_FMT = "%(asctime)s [%(levelname)s] %(name)s :: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

_INSTALLED = False
_ERROR_HANDLER: RotatingFileHandler | None = None
_APP_HANDLER: RotatingFileHandler | None = None
_SCRAPE_HANDLER: RotatingFileHandler | None = None

# Level-tag heuristikleri — print() satırından seviye çıkarmak için
_ERR_RE = re.compile(r"\b(error|hata|exception|traceback|failed|fail|critical)\b", re.IGNORECASE)
_WARN_RE = re.compile(r"\b(warn|uyari|uyarı|deprecat|skipped|atlandı|atlandi)\b", re.IGNORECASE)


def detect_level(line: str) -> str:
    """print() satırından INFO/WARN/ERROR çıkar — UI filtre + disk routing için."""
    if _ERR_RE.search(line):
        return "ERROR"
    if _WARN_RE.search(line):
        return "WARN"
    return "INFO"


def _mk_handler(filename: str, level: int, max_bytes: int = 10 * 1024 * 1024, backups: int = 5) -> RotatingFileHandler:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    h = RotatingFileHandler(
        LOG_DIR / filename,
        maxBytes=max_bytes,
        backupCount=backups,
        encoding="utf-8",
    )
    h.setLevel(level)
    h.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
    return h


def install_disk_logging() -> None:
    """Root logger'a 2 file handler ekle + uvicorn loggerlarını yakala. İdempotent."""
    global _INSTALLED, _ERROR_HANDLER, _APP_HANDLER, _SCRAPE_HANDLER
    if _INSTALLED:
        return

    root = logging.getLogger()
    if root.level > logging.INFO or root.level == logging.NOTSET:
        root.setLevel(logging.INFO)

    _APP_HANDLER = _mk_handler("backend.log", logging.INFO)
    _ERROR_HANDLER = _mk_handler("errors.log", logging.ERROR)
    _SCRAPE_HANDLER = _mk_handler("scrape.log", logging.INFO)

    root.addHandler(_APP_HANDLER)
    root.addHandler(_ERROR_HANDLER)

    # Uvicorn loglarını da yakala (zaten root'a propagate ediyor ama emin olalım)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.INFO)

    # Scraper'lar için ayrı logger — log_buffer.py disk'e bunu yazacak
    scrape_lg = logging.getLogger("multiscout.scrape")
    scrape_lg.setLevel(logging.INFO)
    scrape_lg.addHandler(_SCRAPE_HANDLER)
    scrape_lg.propagate = False  # backend.log'a iki defa yazılmasın

    _INSTALLED = True


def write_print_line(line: str, source: str) -> None:
    """log_buffer Tee'sinin disk'e yazma kancası — her print satırı için çağrılır.

    detect_level ile WARN/ERROR satırları errors.log'a da gider.
    """
    if not _INSTALLED:
        return
    lvl = detect_level(line)
    scrape_lg = logging.getLogger("multiscout.scrape")
    if lvl == "ERROR":
        scrape_lg.error("[%s] %s", source, line)
    elif lvl == "WARN":
        scrape_lg.warning("[%s] %s", source, line)
    else:
        scrape_lg.info("[%s] %s", source, line)


def tail_log_file(filename: str, n: int = 200) -> list[str]:
    """LOG_DIR içindeki bir dosyanın son N satırını döner. Dosya yoksa boş liste."""
    p = LOG_DIR / filename
    if not p.exists():
        return []
    try:
        # Büyük dosyalar için tail — son 1MB'yi oku yeter
        with open(p, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            seek_from = max(0, size - 1_048_576)
            f.seek(seek_from)
            data = f.read().decode("utf-8", errors="replace")
        lines = [ln for ln in data.split("\n") if ln.strip()]
        return lines[-n:]
    except OSError:
        return []


def list_log_files() -> list[dict]:
    """Disk'teki tüm log dosyaları (rotated dahil) + boyut bilgisi."""
    if not LOG_DIR.exists():
        return []
    out = []
    for p in sorted(LOG_DIR.iterdir()):
        if not p.is_file():
            continue
        try:
            out.append({"name": p.name, "size": p.stat().st_size})
        except OSError:
            continue
    return out
