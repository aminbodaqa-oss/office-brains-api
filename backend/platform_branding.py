from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from database import DB_PATH

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_platform_branding_db() -> None:
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL, updated_at TEXT NOT NULL)""")

def get_site_logo() -> str | None:
    with _connect() as conn:
        row = conn.execute("SELECT setting_value FROM platform_settings WHERE setting_key=?", ("site_logo_data_url",)).fetchone()
    return str(row["setting_value"]) if row else None

def save_site_logo(data_url: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("""INSERT INTO platform_settings(setting_key,setting_value,updated_at) VALUES(?,?,?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,updated_at=excluded.updated_at""", ("site_logo_data_url", data_url, now))
