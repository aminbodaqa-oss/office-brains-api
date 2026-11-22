from __future__ import annotations

import os
import sqlite3
from typing import Any
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken

from database import _connect


def _fernet() -> Fernet:
    key = os.getenv("PLATFORM_SECRETS_KEY", "").strip()
    if not key:
        raise RuntimeError("PLATFORM_SECRETS_KEY غير مضبوط. أضف مفتاح تشفير Fernet إلى متغيرات السيرفر أولًا.")
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("PLATFORM_SECRETS_KEY غير صالح. استخدم مفتاح Fernet صحيحًا.") from exc


def init_platform_ai_db() -> None:
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_ai_settings (
            id INTEGER PRIMARY KEY CHECK(id=1),
            provider TEXT NOT NULL DEFAULT 'demo',
            model TEXT NOT NULL DEFAULT '',
            base_url TEXT NOT NULL DEFAULT '',
            timeout_seconds INTEGER NOT NULL DEFAULT 90,
            fallback_provider TEXT NOT NULL DEFAULT 'demo',
            fallback_model TEXT NOT NULL DEFAULT '',
            fallback_base_url TEXT NOT NULL DEFAULT '',
            encrypted_api_key TEXT,
            updated_by TEXT NOT NULL DEFAULT 'system',
            updated_at TEXT NOT NULL
        )""")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(platform_ai_settings)").fetchall()}
        for column, definition in (
            ("fallback_provider", "TEXT NOT NULL DEFAULT 'demo'"),
            ("fallback_model", "TEXT NOT NULL DEFAULT ''"),
            ("fallback_base_url", "TEXT NOT NULL DEFAULT ''"),
        ):
            if column not in columns:
                conn.execute(f"ALTER TABLE platform_ai_settings ADD COLUMN {column} {definition}")
        row = conn.execute("SELECT id FROM platform_ai_settings WHERE id=1").fetchone()
        if row is None:
            provider = os.getenv("BRAIN_PROVIDER", "demo").strip().lower()
            if provider not in {"demo", "gemini", "ollama"}:
                provider = "demo"
            model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash") if provider == "gemini" else os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
            conn.execute("""INSERT INTO platform_ai_settings
                (id,provider,model,base_url,timeout_seconds,updated_by,updated_at)
                VALUES(1,?,?,?,?, 'environment',datetime('now'))""",
                (provider, model, os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
                 max(5, min(int(float(os.getenv("GEMINI_TIMEOUT", "90"))), 180))))


def get_runtime_ai_config() -> dict[str, Any]:
    fallback = {
        "provider": os.getenv("BRAIN_PROVIDER", "demo").strip().lower(),
        "model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        "timeout_seconds": max(5, min(int(float(os.getenv("GEMINI_TIMEOUT", "90"))), 180)),
        "api_key": os.getenv("GEMINI_API_KEY", "").strip(),
    }
    try:
        with _connect() as conn:
            row = conn.execute("SELECT * FROM platform_ai_settings WHERE id=1").fetchone()
        if not row:
            return fallback
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if row["encrypted_api_key"]:
            try:
                api_key = _fernet().decrypt(str(row["encrypted_api_key"]).encode()).decode()
            except (InvalidToken, RuntimeError, UnicodeDecodeError) as exc:
                raise RuntimeError("تعذر فك تشفير مفتاح مزود الذكاء الاصطناعي. راجع PLATFORM_SECRETS_KEY.") from exc
        return {
            "provider": str(row["provider"]),
            "model": str(row["model"]),
            "base_url": str(row["base_url"]).rstrip("/"),
            "timeout_seconds": int(row["timeout_seconds"]),
            "api_key": api_key,
            "fallback_provider": str(row["fallback_provider"] or "demo"),
            "fallback_model": str(row["fallback_model"] or ""),
            "fallback_base_url": str(row["fallback_base_url"] or "").rstrip("/"),
        }
    except sqlite3.Error:
        return fallback


def get_platform_ai_settings() -> dict[str, Any]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM platform_ai_settings WHERE id=1").fetchone()
    if not row:
        return {
            "provider": os.getenv("BRAIN_PROVIDER", "demo").strip().lower(),
            "model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            "base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            "timeout_seconds": 90,
            "has_api_key": bool(os.getenv("GEMINI_API_KEY", "").strip()),
            "key_source": "environment" if os.getenv("GEMINI_API_KEY", "").strip() else "none",
            "updated_by": "environment",
            "updated_at": None,
        }
    env_key = bool(os.getenv("GEMINI_API_KEY", "").strip())
    return {
        "provider": row["provider"],
        "model": row["model"],
        "base_url": row["base_url"],
        "timeout_seconds": row["timeout_seconds"],
        "fallback_provider": row["fallback_provider"],
        "fallback_model": row["fallback_model"],
        "fallback_base_url": row["fallback_base_url"],
        "has_api_key": bool(row["encrypted_api_key"] or env_key),
        "key_source": "database" if row["encrypted_api_key"] else ("environment" if env_key else "none"),
        "updated_by": row["updated_by"],
        "updated_at": row["updated_at"],
    }


def save_platform_ai_settings(provider: str, model: str, base_url: str,
                              timeout_seconds: int, api_key: str | None,
                              clear_api_key: bool, actor: str,
                              fallback_provider: str = "demo",
                              fallback_model: str = "",
                              fallback_base_url: str = "") -> dict[str, Any]:
    provider = provider.strip().lower()
    model = model.strip()
    base_url = base_url.strip().rstrip("/")
    if provider not in {"demo", "gemini", "ollama"} or fallback_provider not in {"demo", "gemini", "ollama"}:
        raise ValueError("مزود الذكاء الاصطناعي غير مدعوم.")
    fallback_model = fallback_model.strip()
    fallback_base_url = fallback_base_url.strip().rstrip("/")
    if fallback_provider != "demo" and not fallback_model:
        raise ValueError("اسم نموذج المزود الاحتياطي مطلوب.")
    if fallback_base_url:
        parsed_fallback = urlparse(fallback_base_url)
        if parsed_fallback.scheme not in {"http", "https"} or not parsed_fallback.netloc:
            raise ValueError("عنوان المزود الاحتياطي يجب أن يكون رابط HTTP أو HTTPS صحيحًا.")
    if not model or len(model) > 160:
        raise ValueError("اسم النموذج مطلوب وبحد أقصى 160 حرفًا.")
    if timeout_seconds < 5 or timeout_seconds > 180:
        raise ValueError("المهلة يجب أن تكون بين 5 و180 ثانية.")
    if provider == "ollama":
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("عنوان Ollama يجب أن يكون رابط HTTP أو HTTPS صحيحًا.")
    encrypted = None
    with _connect() as conn:
        existing = conn.execute("SELECT encrypted_api_key FROM platform_ai_settings WHERE id=1").fetchone()
        if clear_api_key:
            encrypted = None
        elif api_key:
            if len(api_key) < 10 or len(api_key) > 500:
                raise ValueError("مفتاح API غير صالح.")
            encrypted = _fernet().encrypt(api_key.encode()).decode()
        elif existing:
            encrypted = existing["encrypted_api_key"]
        conn.execute("""INSERT INTO platform_ai_settings
            (id,provider,model,base_url,timeout_seconds,fallback_provider,fallback_model,
             fallback_base_url,encrypted_api_key,updated_by,updated_at)
            VALUES(1,?,?,?,?,?,?,?,?,?,datetime('now'))
            ON CONFLICT(id) DO UPDATE SET provider=excluded.provider,model=excluded.model,
            base_url=excluded.base_url,timeout_seconds=excluded.timeout_seconds,
            fallback_provider=excluded.fallback_provider,fallback_model=excluded.fallback_model,
            fallback_base_url=excluded.fallback_base_url,encrypted_api_key=excluded.encrypted_api_key,
            updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
            (provider, model, base_url, timeout_seconds, fallback_provider, fallback_model,
             fallback_base_url, encrypted, actor))
        conn.execute("""INSERT INTO platform_audit_log(actor,action,entity_type,entity_id,created_at)
            VALUES(?,?,?,?,datetime('now'))""", (actor, "ai_provider_settings_updated", "platform", "ai"))
    return get_platform_ai_settings()
