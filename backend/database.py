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
        conn.execute("""CREATE TABLE IF NOT EXISTS push_devices (
            token TEXT PRIMARY KEY, platform TEXT NOT NULL DEFAULT 'android',
            device_id TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS push_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT, notification_id INTEGER NOT NULL,
            token TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, sent_at TEXT)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_push_outbox_status ON push_outbox(status,id)")
        conn.execute("""CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
            title TEXT NOT NULL, message TEXT NOT NULL, details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0)""")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(notifications)").fetchall()}
        if "employee_id" not in columns:
            conn.execute("ALTER TABLE notifications ADD COLUMN employee_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_employee ON notifications(employee_id,created_at DESC)")

def delete_chat_interactions(employee_id: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM interactions WHERE employee_id=? AND interaction_type IN ('chat','proactive_chat')",
            (employee_id,))
        return int(cur.rowcount)


def get_chat_history(employee_id: str, limit: int = 100) -> list[dict[str, str]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT payload FROM interactions WHERE employee_id=? AND interaction_type IN ('chat','proactive_chat') ORDER BY id DESC LIMIT ?",
            (employee_id, max(1, min(int(limit), 200))),
        ).fetchall()
    messages: list[dict[str, str]] = []
    for row in reversed(rows):
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            continue
        history = payload.get("messages") or []
        last_user = next((item for item in reversed(history) if item.get("role") == "user"), None)
        if last_user and last_user.get("content"):
            messages.append({"role": "user", "content": str(last_user["content"])})
        response = payload.get("response")
        if response:
            messages.append({"role": "assistant", "content": str(response)})
    return messages[-200:]


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


def add_notification(event_type: str, title: str, message: str, details: str = "",
                    employee_id: str | None = None) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO notifications(event_type,title,message,details,created_at,is_read,employee_id) VALUES(?,?,?,?,?,0,?)",
            (event_type[:40], title[:180], message[:1000], details[:12000], now, employee_id))
        notification_id = int(cur.lastrowid)
        devices = conn.execute("SELECT token FROM push_devices WHERE active=1").fetchall()
        for device in devices:
            conn.execute(
                "INSERT INTO push_outbox(notification_id,token,status,attempts,last_error,created_at) VALUES(?,?,'pending',0,'',?)",
                (notification_id, device["token"], now))
        return notification_id


def register_push_device(token: str, platform: str = "android", device_id: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO push_devices(token,platform,device_id,active,created_at,updated_at)
               VALUES(?,?,?,1,?,?)
               ON CONFLICT(token) DO UPDATE SET platform=excluded.platform,device_id=excluded.device_id,
               active=1,updated_at=excluded.updated_at""",
            (token, platform[:20], device_id[:128], now, now))


def unregister_push_device(token: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE push_devices SET active=0,updated_at=? WHERE token=?",
                     (datetime.now(timezone.utc).isoformat(), token))
        conn.execute("UPDATE push_outbox SET status='cancelled' WHERE token=? AND status='pending'", (token,))


def pending_pushes(limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT o.id,o.notification_id,o.token,o.attempts,n.title,n.message,n.employee_id
               FROM push_outbox o JOIN notifications n ON n.id=o.notification_id
               WHERE o.status='pending' ORDER BY o.id LIMIT ?""",
            (max(1, min(int(limit), 100)),)).fetchall()
    return [dict(row) for row in rows]


def finish_push(push_id: int, success: bool, error: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        row = conn.execute("SELECT attempts FROM push_outbox WHERE id=?", (push_id,)).fetchone()
        if not row:
            return
        attempts = int(row["attempts"]) + 1
        status = "sent" if success else ("failed" if attempts >= 5 else "pending")
        conn.execute(
            "UPDATE push_outbox SET status=?,attempts=?,last_error=?,sent_at=? WHERE id=?",
            (status, attempts, error[:500], now if success else None, push_id))


def deactivate_push_device(token: str) -> None:
    unregister_push_device(token)


def get_push_status() -> dict[str, int]:
    with _connect() as conn:
        active = int(conn.execute("SELECT COUNT(*) FROM push_devices WHERE active=1").fetchone()[0])
        pending = int(conn.execute("SELECT COUNT(*) FROM push_outbox WHERE status='pending'").fetchone()[0])
        sent = int(conn.execute("SELECT COUNT(*) FROM push_outbox WHERE status='sent'").fetchone()[0])
        failed = int(conn.execute("SELECT COUNT(*) FROM push_outbox WHERE status='failed'").fetchone()[0])
    return {"active_devices": active, "pending": pending, "sent": sent, "failed": failed}

def get_notifications(limit: int = 50, unread_only: bool = False) -> dict[str, Any]:
    limit = max(1, min(int(limit), 100))
    with _connect() as conn:
        where = "WHERE is_read=0" if unread_only else ""
        rows = conn.execute(
            f"SELECT id,event_type,title,message,details,created_at,is_read,employee_id FROM notifications {where} ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
        unread = conn.execute("SELECT COUNT(*) FROM notifications WHERE is_read=0").fetchone()[0]
    return {"notifications": [dict(r) for r in rows], "unread_count": int(unread)}


def delete_notifications(notification_ids: list[int] | None = None, all_items: bool = False) -> int:
    with _connect() as conn:
        if all_items:
            cur = conn.execute("DELETE FROM notifications")
        elif notification_ids:
            ids = [int(x) for x in notification_ids[:100] if int(x) > 0]
            if not ids:
                return 0
            marks = ",".join("?" for _ in ids)
            cur = conn.execute(f"DELETE FROM notifications WHERE id IN ({marks})", ids)
        else:
            return 0
        return int(cur.rowcount)

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
