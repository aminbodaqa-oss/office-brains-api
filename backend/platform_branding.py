from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from database import _connect


SITE_SETTING_LIMITS = {
    "site_name": 100,
    "page_title": 160,
    "meta_description": 320,
    "hero_title": 160,
    "hero_emphasis": 160,
    "hero_subtitle": 700,
    "primary_cta_text": 80,
    "primary_cta_url": 300,
    "about_title": 160,
    "about_description": 700,
    "cta_title": 160,
    "cta_description": 500,
    "footer_text": 200,
    "brand_primary": 7,
    "brand_accent": 7,
    "brand_highlight": 7,
}


def init_platform_branding_db() -> None:
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")


def get_site_logo() -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT setting_value FROM platform_settings WHERE setting_key=?",
            ("site_logo_data_url",),
        ).fetchone()
    return str(row["setting_value"]) if row else None


def save_site_logo(data_url: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("""INSERT INTO platform_settings(setting_key,setting_value,updated_at)
            VALUES(?,?,?) ON CONFLICT(setting_key) DO UPDATE SET
            setting_value=excluded.setting_value,updated_at=excluded.updated_at""",
            ("site_logo_data_url", data_url, now))


def get_site_settings() -> dict[str, str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT setting_key,setting_value FROM platform_settings WHERE setting_key LIKE 'site_%' OR setting_key LIKE 'brand_%'"
        ).fetchall()
    return {str(row["setting_key"]): str(row["setting_value"]) for row in rows
            if row["setting_key"] != "site_logo_data_url"}


def save_site_settings(settings: dict[str, Any], actor: str) -> dict[str, str]:
    unknown = set(settings) - set(SITE_SETTING_LIMITS)
    if unknown:
        raise ValueError("يوجد حقل غير مسموح به في إعدادات الموقع.")
    cleaned: dict[str, str] = {}
    for key, raw in settings.items():
        value = str(raw).strip()
        if len(value) > SITE_SETTING_LIMITS[key]:
            raise ValueError("القيمة أطول من الحد المسموح للحقل: " + key)
        if key.startswith("brand_") and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("ألوان الهوية يجب أن تكون بصيغة HEX مثل #00A884.")
        if key == "primary_cta_url":
            parsed = urlparse(value)
            if parsed.scheme and parsed.scheme != "https":
                raise ValueError("رابط زر الدعوة يجب أن يكون HTTPS أو رابطًا داخليًا.")
            if value.startswith("//") or ".." in value:
                raise ValueError("رابط زر الدعوة غير مسموح.")
        cleaned[key] = value
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        for key, value in cleaned.items():
            conn.execute("""INSERT INTO platform_settings(setting_key,setting_value,updated_at)
                VALUES(?,?,?) ON CONFLICT(setting_key) DO UPDATE SET
                setting_value=excluded.setting_value,updated_at=excluded.updated_at""",
                (key, value, now))
        conn.execute("""INSERT INTO platform_audit_log(actor,action,entity_type,entity_id,created_at)
            VALUES(?,?,?,?,?)""",
            (actor, "website_branding_updated", "platform", "website", now))
    return get_site_settings()
