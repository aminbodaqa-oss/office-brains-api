from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database import _connect

_scheme = HTTPBearer(auto_error=False)
TENANT_TOKEN_TTL_SECONDS = int(os.getenv("TENANT_TOKEN_TTL_SECONDS", "3600"))


def _secret() -> bytes:
    value = os.getenv("TENANT_AUTH_SECRET", "").strip()
    if len(value) < 32:
        raise RuntimeError("TENANT_AUTH_SECRET must contain at least 32 characters")
    return value.encode("utf-8")


def _b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_tenant_token(user_id: str, workspace_id: str, role: str) -> str:
    if role not in {"owner", "admin", "member"}:
        raise ValueError("Invalid tenant role")
    payload = {
        "sub": user_id,
        "workspace_id": workspace_id,
        "role": role,
        "aud": "office-brains-tenant",
        "exp": int(time.time()) + max(300, min(TENANT_TOKEN_TTL_SECONDS, 86400)),
    }
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64e(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return body + "." + signature


def verify_tenant_token(token: str) -> dict[str, str] | None:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
        supplied = _b64d(signature)
        if not hmac.compare_digest(expected, supplied):
            return None
        payload: dict[str, Any] = json.loads(_b64d(body))
        user_id = str(payload.get("sub", ""))
        workspace_id = str(payload.get("workspace_id", ""))
        role = str(payload.get("role", ""))
        if (payload.get("aud") != "office-brains-tenant"
                or not user_id or not workspace_id
                or role not in {"owner", "admin", "member"}
                or int(payload.get("exp", 0)) <= int(time.time())):
            return None
        return {"user_id": user_id, "workspace_id": workspace_id, "role": role}
    except (ValueError, TypeError, RuntimeError, json.JSONDecodeError):
        return None


async def require_tenant_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_scheme),
) -> dict[str, str]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول إلى مساحة العمل.")
    claims = verify_tenant_token(credentials.credentials)
    if not claims:
        raise HTTPException(status_code=401, detail="جلسة مساحة العمل غير صالحة أو انتهت.")

    with _connect() as conn:
        row = conn.execute(
            """SELECT u.id AS user_id,u.status AS user_status,
                      m.workspace_id,m.role,m.status AS membership_status,
                      w.status AS workspace_status,c.status AS customer_status
               FROM tenant_users u
               JOIN tenant_memberships m ON m.user_id=u.id
               JOIN platform_workspaces w ON w.id=m.workspace_id
               JOIN platform_customers c ON c.id=w.customer_id
               WHERE u.id=? AND m.workspace_id=?""",
            (claims["user_id"], claims["workspace_id"]),
        ).fetchone()

    if (row is None or row["user_status"] != "active"
            or row["membership_status"] != "active"
            or row["workspace_status"] not in {"trial", "active"}
            or row["customer_status"] not in {"trial", "active"}
            or row["role"] != claims["role"]):
        raise HTTPException(status_code=403, detail="الحساب أو مساحة العمل غير مفعّلة.")
    return claims
