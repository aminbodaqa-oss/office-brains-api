from __future__ import annotations
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = os.getenv("DATABASE_PATH", "./data/office_brains.sqlite3")

def _connect() -> sqlite3.Connection:
    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def get_owner_password_hash(fallback: str = "") -> str:
    with _connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS owner_credentials (id INTEGER PRIMARY KEY CHECK(id=1), password_hash TEXT NOT NULL, updated_at TEXT NOT NULL)")
        row = conn.execute("SELECT password_hash FROM owner_credentials WHERE id=1").fetchone()
    return str(row["password_hash"]) if row else fallback


def set_owner_password_hash(password_hash: str) -> None:
    with _connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS owner_credentials (id INTEGER PRIMARY KEY CHECK(id=1), password_hash TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.execute("INSERT INTO owner_credentials(id,password_hash,updated_at) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET password_hash=excluded.password_hash, updated_at=excluded.updated_at",
                     (password_hash, datetime.now(timezone.utc).isoformat()))


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL,
            interaction_type TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL,
            content TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS autonomous_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_date TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
            summary TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '')""")
        conn.execute("""CREATE TABLE IF NOT EXISTS autonomous_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_date TEXT NOT NULL,
            employee_id TEXT NOT NULL, department TEXT NOT NULL, content TEXT NOT NULL,
            created_at TEXT NOT NULL, UNIQUE(run_date, employee_id))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
            title TEXT NOT NULL, message TEXT NOT NULL, details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at DESC)")

def delete_chat_interactions(employee_id: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM interactions WHERE employee_id=? AND interaction_type='chat'",
            (employee_id,))
        return int(cur.rowcount)


def log_interaction(employee_id: str, interaction_type: str, payload: dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute("INSERT INTO interactions(employee_id, interaction_type, payload, created_at) VALUES(?,?,?,?)",
            (employee_id, interaction_type, json.dumps(payload, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))

def add_memory(employee_id: str, content: str, tags: list[str] | None = None) -> int:
    with _connect() as conn:
        cur = conn.execute("INSERT INTO memories(employee_id, content, tags, created_at) VALUES(?,?,?,?)",
            (employee_id, content, json.dumps(tags or [], ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
        return int(cur.lastrowid)

def get_memories(employee_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT id, content, tags, created_at FROM memories WHERE employee_id=? ORDER BY id DESC LIMIT ?",
            (employee_id, max(1, min(limit, 100)))).fetchall()
    return [{"id": r["id"], "content": r["content"], "tags": json.loads(r["tags"]), "created_at": r["created_at"]} for r in rows]


def add_notification(event_type: str, title: str, message: str, details: str = "") -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO notifications(event_type,title,message,details,created_at,is_read) VALUES(?,?,?,?,?,0)",
            (event_type[:40], title[:180], message[:1000], details[:12000],
             datetime.now(timezone.utc).isoformat()))
        return int(cur.lastrowid)

def get_notifications(limit: int = 50, unread_only: bool = False) -> dict[str, Any]:
    limit = max(1, min(int(limit), 100))
    with _connect() as conn:
        where = "WHERE is_read=0" if unread_only else ""
        rows = conn.execute(
            f"SELECT id,event_type,title,message,details,created_at,is_read FROM notifications {where} ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
        unread = conn.execute("SELECT COUNT(*) FROM notifications WHERE is_read=0").fetchone()[0]
    return {"notifications": [dict(r) for r in rows], "unread_count": int(unread)}

def mark_notifications_read(notification_ids: list[int] | None = None, all_read: bool = False) -> int:
    with _connect() as conn:
        if all_read:
            cur = conn.execute("UPDATE notifications SET is_read=1 WHERE is_read=0")
        elif notification_ids:
            ids = [int(x) for x in notification_ids[:100] if int(x) > 0]
            if not ids:
                return 0
            marks = ",".join("?" for _ in ids)
            cur = conn.execute(f"UPDATE notifications SET is_read=1 WHERE id IN ({marks})", ids)
        else:
            return 0
        return int(cur.rowcount)
