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
