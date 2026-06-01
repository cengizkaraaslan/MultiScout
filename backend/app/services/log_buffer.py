"""Hafif in-memory log ring buffer.

Backend scraper print() çıktılarını yakalayıp son N satırı bellekte tutar.
Frontend admin "Loglar" sekmesi bu buffer'dan polling ile okur.

Kullanım: app startup'ta install_log_capture() çağrılır → sys.stdout/stderr
ring buffer'a da yazar (orijinal stdout korunur).
"""
from __future__ import annotations

import re
import sys
import threading
from collections import deque
from datetime import datetime
from typing import Iterable

_MAX = 2000
_LOCK = threading.Lock()
_BUF: deque[dict] = deque(maxlen=_MAX)

# [Trendyol] / [Karaca] / [N11] gibi tag'ler — platform filter için
_TAG_RE = re.compile(r"^\[([A-Za-z][\w]+)\]")


def _platform_from_line(line: str) -> str | None:
    m = _TAG_RE.match(line.strip())
    if not m:
        return None
    return m.group(1).lower()


def _push(line: str, source: str) -> None:
    line = line.rstrip()
    if not line:
        return
    # Disk'e de yaz (logging_config.install_disk_logging() çağrıldıysa)
    try:
        from app.core.logging_config import write_print_line, detect_level
        write_print_line(line, source)
        level = detect_level(line)
    except Exception:
        level = "INFO"
    with _LOCK:
        _BUF.append({
            "ts": datetime.utcnow().isoformat() + "Z",
            "platform": _platform_from_line(line),
            "src": source,
            "level": level,
            "msg": line[:1000],
        })


class _Tee:
    """Hem orijinal stream'e hem ring buffer'a yazar."""

    def __init__(self, original, source: str):
        self._orig = original
        self._src = source
        self._partial = ""

    def write(self, data: str) -> int:
        try:
            written = self._orig.write(data)
        except Exception:
            written = len(data)
        # Satır satır buffer'a ekle
        buf = self._partial + data
        lines = buf.split("\n")
        self._partial = lines[-1]
        for ln in lines[:-1]:
            _push(ln, self._src)
        return written

    def flush(self) -> None:
        try:
            self._orig.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._orig, name)


_INSTALLED = False


def install_log_capture() -> None:
    """sys.stdout/stderr'ı Tee ile sarmala. İdempotent — bir kez sarmalayıp bırakır."""
    global _INSTALLED
    if _INSTALLED:
        return
    sys.stdout = _Tee(sys.stdout, "out")  # type: ignore[assignment]
    sys.stderr = _Tee(sys.stderr, "err")  # type: ignore[assignment]
    _INSTALLED = True


def get_log_lines(
    limit: int = 200,
    platform_filter: str | None = None,
    level_filter: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """Son N satırı döner (en eski → en yeni).

    level_filter: "ERROR" / "WARN" / "INFO" (sadece bu seviye ve üstü)
    search: substring (case-insensitive)
    """
    pf = platform_filter.lower().strip() if platform_filter else None
    lf = level_filter.upper().strip() if level_filter else None
    sq = search.lower().strip() if search else None
    with _LOCK:
        rows: Iterable[dict] = list(_BUF)
    if pf:
        rows = [r for r in rows if r.get("platform") == pf]
    if lf == "ERROR":
        rows = [r for r in rows if r.get("level") == "ERROR"]
    elif lf == "WARN":
        rows = [r for r in rows if r.get("level") in ("ERROR", "WARN")]
    if sq:
        rows = [r for r in rows if sq in r.get("msg", "").lower()]
    rows = list(rows)
    if len(rows) > limit:
        rows = rows[-limit:]
    return rows
