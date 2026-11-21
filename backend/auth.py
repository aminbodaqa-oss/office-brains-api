from __future__ import annotations
import base64, hashlib, hmac, json, os, secrets, time
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

TOKEN_TTL_SECONDS = int(os.getenv("OFFICE_TOKEN_TTL_SECONDS", "1800"))
bearer_scheme = HTTPBearer(auto_error=False)

def _b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def hash_password(password: str, salt: bytes | None = None, iterations: int = 310000) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64e(salt)}${_b64e(digest)}"

def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _b64d(salt), int(rounds))
        return hmac.compare_digest(actual, _b64d(expected))
    except (ValueError, TypeError):
        return False

def _secret() -> bytes:
    value = os.getenv("OFFICE_AUTH_SECRET", "").strip()
    if len(value) < 32:
        raise RuntimeError("OFFICE_AUTH_SECRET must contain at least 32 characters")
    return value.encode("utf-8")

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_token(username: str) -> str:
    payload = {"sub": username, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64e(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return body + "." + signature

def verify_token(token: str) -> str | None:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64d(signature)):
            return None
        payload = json.loads(_b64d(body))
        username = str(payload.get("sub", ""))
        if not username or int(payload.get("exp", 0)) < int(time.time()):
            return None
        return username
    except (ValueError, TypeError, RuntimeError, json.JSONDecodeError):
        return None

async def require_owner(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="سجّل الدخول أولًا")
    username = verify_token(credentials.credentials)
    expected = os.getenv("OWNER_USERNAME", "").strip()
    if not username or not expected or not hmac.compare_digest(username, expected):
        raise HTTPException(status_code=401, detail="انتهت جلسة الدخول أو أنها غير صالحة")
    return username
