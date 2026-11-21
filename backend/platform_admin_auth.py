from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_scheme = HTTPBearer(auto_error=False)


def _secret() -> bytes:
    value = os.getenv("PLATFORM_ADMIN_AUTH_SECRET", "").strip()
    if len(value) < 32:
        raise RuntimeError("PLATFORM_ADMIN_AUTH_SECRET must contain at least 32 characters")
    return value.encode("utf-8")


def issue_platform_token(username: str) -> str:
    payload = {"sub": username, "aud": "office-brains-platform-admin", "exp": int(time.time()) + 900}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
    signature = base64.urlsafe_b64encode(hmac.new(_secret(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return body + "." + signature


def verify_platform_token(token: str) -> str | None:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, supplied):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        username = str(payload.get("sub", ""))
        if payload.get("aud") != "office-brains-platform-admin" or not username or int(payload.get("exp", 0)) <= int(time.time()):
            return None
        configured = os.getenv("PLATFORM_ADMIN_USERNAME", "").strip()
        if not configured or not hmac.compare_digest(username, configured):
            return None
        return username
    except (ValueError, TypeError, RuntimeError, json.JSONDecodeError):
        return None


async def require_platform_admin(credentials: HTTPAuthorizationCredentials | None = Depends(_scheme)) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="يلزم تسجيل دخول مالك المنصة.")
    username = verify_platform_token(credentials.credentials)
    if not username:
        raise HTTPException(status_code=401, detail="جلسة Super Admin غير صالحة أو انتهت.")
    return username
