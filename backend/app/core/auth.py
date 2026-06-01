import os
from fastapi import Header, HTTPException, status

_API_KEY = os.getenv("API_KEY", "").strip()

if not _API_KEY:
    print("[AUTH] API_KEY env var not set — protected endpoints are OPEN. Set API_KEY for production.", flush=True)


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-KEY")):
    if not _API_KEY:
        return True
    if x_api_key != _API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-API-KEY")
    return True
