from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from database import _connect


DEFAULTS = {
    "public_site_enabled": "true",
    "allow_customer_creation": "true",
    "site_notice_enabled": "false",
    "site_notice_text": "",
}


def init_platform_settings_db() -> None:
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_control_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        now = datetime.now(timezone.utc).isoformat()
        for key, value in DEFAULTS.items():
            conn.execute("""INSERT OR IGNORE INTO platform_control_settings
                (setting_key,setting_value,updated_by,updated_at) VALUES(?,?,?,?)""",
                (key, value, "system", now))


def get_platform_settings() -> dict[str, Any]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT setting_key,setting_value FROM platform_control_settings"
        ).fetchall()
    values = dict(DEFAULTS)
    values.update({str(row["setting_key"]): str(row["setting_value"]) for row in rows})
    return {
        "public_site_enabled": values["public_site_enabled"] == "true",
        "allow_customer_creation": values["allow_customer_creation"] == "true",
        "site_notice_enabled": values["site_notice_enabled"] == "true",
        "site_notice_text": values["site_notice_text"],
    }


def save_platform_settings(settings: dict[str, Any], actor: str) -> dict[str, Any]:
    allowed = set(DEFAULTS)
    if set(settings) - allowed:
        raise ValueError("يوجد إعداد غير معروف.")
    cleaned: dict[str, str] = {}
    for key, value in settings.items():
        if key == "site_notice_text":
            text = str(value).strip()
            if len(text) > 500:
                raise ValueError("رسالة التنويه يجب ألا تتجاوز 500 حرف.")
            cleaned[key] = text
        else:
            if not isinstance(value, bool):
                raise ValueError("إعدادات التفعيل يجب أن تكون true أو false.")
            cleaned[key] = "true" if value else "false"
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        for key, value in cleaned.items():
            conn.execute("""INSERT INTO platform_control_settings
                (setting_key,setting_value,updated_by,updated_at) VALUES(?,?,?,?)
                ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,
                updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
                (key, value, actor, now))
        conn.execute("""INSERT INTO platform_audit_log(actor,action,entity_type,entity_id,created_at)
            VALUES(?,?,?,?,?)""", (actor, "platform_settings_updated", "platform", "settings", now))
    return get_platform_settings()
