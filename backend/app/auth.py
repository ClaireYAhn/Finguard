"""Admin session cookie (single password from env) and app-key authentication."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import HTTPException, Request

from registry import store as registry

from .config import get_settings

COOKIE = "fg_session"
SESSION_TTL = 8 * 3600
_RUNTIME_SECRET = secrets.token_hex(32)
_attempts: dict[str, list[float]] = {}


def _secret() -> bytes:
    return (get_settings().session_secret or _RUNTIME_SECRET).encode()


def make_session() -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"exp": int(time.time()) + SESSION_TTL, "n": secrets.token_hex(4)}).encode()).decode()
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_session(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    payload, sig = token.rsplit(".", 1)
    good = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, good):
        return False
    try:
        return json.loads(base64.urlsafe_b64decode(payload.encode()))["exp"] > time.time()
    except Exception:  # noqa: BLE001
        return False


def check_password(pw: str, client: str = "?") -> bool:
    now = time.time()
    recent = [t for t in _attempts.get(client, []) if now - t < 60]
    if len(recent) >= 10:
        raise HTTPException(429, "Too many login attempts. Wait a minute and try again.")
    ok = hmac.compare_digest(pw.encode(), get_settings().admin_password.encode())
    if not ok:
        recent.append(now)
    _attempts[client] = recent
    return ok


def require_admin(request: Request) -> None:
    if not verify_session(request.cookies.get(COOKIE)):
        raise HTTPException(401, "Please sign in to the control panel.")


def extract_key(request: Request) -> str | None:
    k = request.headers.get("x-api-key")
    if k:
        return k.strip()
    a = request.headers.get("authorization", "")
    if a.lower().startswith("bearer "):
        return a[7:].strip()
    return None


class AuthError(Exception):
    def __init__(self, message: str, status: int = 401) -> None:
        super().__init__(message)
        self.status = status


def authenticate_app(request: Request) -> dict[str, Any]:
    key = extract_key(request)
    if not key:
        raise AuthError("Missing FinGuard app key. Send it as x-api-key or Authorization: Bearer.")
    app = registry.get_by_key(key)
    if not app:
        raise AuthError("Invalid FinGuard app key.")
    if not app["enabled"]:
        raise AuthError("This application is disabled in the FinGuard registry.", 403)
    return app
