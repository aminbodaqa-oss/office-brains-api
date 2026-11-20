from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from database import _connect
from employees import EMPLOYEES, EMPLOYEE_IDS


def init_internal_messaging_db() -> None:
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS internal_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT NOT NULL,
            recipient_id TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'delivered',
            created_at TEXT NOT NULL,
            read_at TEXT
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_internal_inbox ON internal_messages(recipient_id,id DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_internal_sent ON internal_messages(sender_id,id DESC)")


def send_internal_message(sender_id: str, recipient_id: str, content: str) -> dict[str, Any]:
    if sender_id not in EMPLOYEE_IDS or recipient_id not in EMPLOYEE_IDS:
        raise ValueError("اسم الموظف غير موجود.")
    if sender_id == recipient_id:
        raise ValueError("لا يمكن إرسال رسالة للموظف نفسه.")
    body = content.strip()[:6000]
    if not body:
        raise ValueError("محتوى الرسالة فارغ.")
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO internal_messages(sender_id,recipient_id,content,status,created_at) VALUES(?,?,?,'delivered',?)",
            (sender_id, recipient_id, body, now),
        )
        row = conn.execute("SELECT * FROM internal_messages WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


def list_internal_messages(employee_id: str, folder: str = "inbox", limit: int = 30) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    column = "recipient_id" if folder == "inbox" else "sender_id"
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM internal_messages WHERE {column}=? ORDER BY id DESC LIMIT ?",
            (employee_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def mark_internal_inbox_read(employee_id: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE internal_messages SET status='read',read_at=? WHERE recipient_id=? AND status='delivered'",
            (now, employee_id),
        )
        return int(cur.rowcount)


def mark_internal_message_read(message_id: int, employee_id: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE internal_messages SET status='read',read_at=? WHERE id=? AND recipient_id=? AND status='delivered'",
            (now, int(message_id), employee_id),
        )
        return cur.rowcount > 0


def _normalize_with_positions(value: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    positions: list[int] = []
    for index, char in enumerate(value.lower()):
        if char in "أإآ":
            char = "ا"
        elif char == "ى":
            char = "ي"
        elif char == "ؤ":
            char = "و"
        elif char == "ئ":
            char = "ي"
        if char in "ًٌٍَُِّْـ":
            continue
        chars.append(char)
        positions.append(index)
    return "".join(chars), positions


def detect_send_request(value: str) -> dict[str, str] | None:
    normalized, positions = _normalize_with_positions(value)
    verbs = r"(?:ابعتي|ابعت|ابعثي|ابعث|ارسلي|ارسل|تبعتي|تبعت|تبعثي|تبعث|بلغي|بلغ|راسلي|راسل|كلمي|كلم)"
    names = sorted(EMPLOYEE_IDS, key=len, reverse=True)
    aliases: dict[str, str] = {}
    for name in names:
        key, _ = _normalize_with_positions(name)
        aliases[key] = name
    alternatives = "|".join(re.escape(name) for name in aliases)
    pattern = re.compile(
        rf"(?:^|\s){verbs}\s+(?:(?:رساله|مسج)\s+)?(?:ل|الي)?\s*(?:يا\s*)?(?P<recipient>{alternatives})(?:\s+(?P<body>.*))?$"
    )
    match = pattern.search(normalized)
    if not match:
        return None
    recipient = aliases.get(match.group("recipient"), "")
    body_start = match.start("body") if match.group("body") else -1
    if body_start < 0 or not match.group("body").strip():
        body = ""
    else:
        original_start = positions[body_start]
        body = value[original_start:].strip(" \t،,:؛-")
    return {"recipient_id": recipient, "content": body}


def has_send_intent(value: str) -> bool:
    normalized, _ = _normalize_with_positions(value)
    return bool(re.search(r"(?:ابعتي|ابعت|ابعثي|ابعث|ارسلي|ارسل|تبعتي|تبعت|تبعثي|تبعث|بلغي|بلغ|راسلي|راسل|كلمي|كلم)", normalized))
