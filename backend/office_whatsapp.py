from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from database import _connect
from employees import EMPLOYEES, EMPLOYEE_IDS

# Clearly fictional, non-dialable extensions: these are not telephone numbers.
def virtual_number(employee_id: str) -> str:
    if employee_id == "المالك":
        return "VO-000"
    ids = [item["id"] for item in EMPLOYEES]
    if employee_id not in ids:
        raise ValueError("الموظف غير موجود.")
    return f"VO-{ids.index(employee_id)+1:03d}"

def init_whatsapp_db() -> None:
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS office_whatsapp_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT NOT NULL,
            recipient_id TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            read_at TEXT
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_wa_inbox ON office_whatsapp_messages(recipient_id,id DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_wa_pair ON office_whatsapp_messages(sender_id,recipient_id,id DESC)")

def whatsapp_contacts() -> list[dict[str, str]]:
    return [{"id": item["id"], "role": item["role"], "department": item["department"],
             "virtual_number": virtual_number(item["id"])} for item in EMPLOYEES]


def detect_whatsapp_send_request(value: str) -> dict[str, str] | None:
    import re
    aliases = {item["id"]: item["id"] for item in EMPLOYEES}
    names = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
    match = re.search(
        rf"(?:ابعتي|ابعت|ابعثي|ابعث|ارسلي|ارسل|بلغي|بلغ)\s+(?:رسالة\s+)?واتساب\s+(?:ل|الى|إلى)?\s*(?P<recipient>{names})\s*(?:[:：-]\s*|\s+)(?P<content>.+)$",
        value.strip(), re.IGNORECASE)
    if not match:
        return None
    return {"recipient_id": match.group("recipient"), "content": match.group("content").strip()}

def send_whatsapp_message(sender_id: str, recipient_id: str, content: str) -> dict[str, Any]:
    if sender_id not in EMPLOYEE_IDS | {"المالك"} or recipient_id not in EMPLOYEE_IDS:
        raise ValueError("اسم الموظف غير موجود.")
    if sender_id == recipient_id:
        raise ValueError("لا يمكن مراسلة نفسك.")
    body = content.strip()
    if not body or len(body) > 6000:
        raise ValueError("اكتب رسالة من 1 إلى 6000 حرف.")
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO office_whatsapp_messages(sender_id,recipient_id,content,created_at) VALUES(?,?,?,?)",
            (sender_id, recipient_id, body, now))
        row = conn.execute("SELECT * FROM office_whatsapp_messages WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)

def list_whatsapp_messages(employee_id: str, peer_id: str, limit: int = 100) -> list[dict[str, Any]]:
    if employee_id not in EMPLOYEE_IDS | {"المالك"} or peer_id not in EMPLOYEE_IDS:
        raise ValueError("اسم الموظف غير موجود.")
    limit = max(1, min(int(limit), 200))
    with _connect() as conn:
        rows = conn.execute("""SELECT * FROM office_whatsapp_messages
            WHERE (sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?)
            ORDER BY id DESC LIMIT ?""", (employee_id, peer_id, peer_id, employee_id, limit)).fetchall()
        conn.execute("""UPDATE office_whatsapp_messages SET read_at=?
            WHERE sender_id=? AND recipient_id=? AND read_at IS NULL""",
            (datetime.now(timezone.utc).isoformat(), peer_id, employee_id))
    return [dict(row) for row in reversed(rows)]

def list_whatsapp_inbox(employee_id: str, limit: int = 20) -> list[dict[str, Any]]:
    if employee_id not in EMPLOYEE_IDS:
        raise ValueError("اسم الموظف غير موجود.")
    with _connect() as conn:
        rows = conn.execute("""SELECT m.*, (SELECT COUNT(*) FROM office_whatsapp_messages u
            WHERE u.sender_id=m.sender_id AND u.recipient_id=? AND u.read_at IS NULL) AS unread_count
            FROM office_whatsapp_messages m
            WHERE m.id IN (SELECT MAX(id) FROM office_whatsapp_messages
              WHERE sender_id=? OR recipient_id=? GROUP BY CASE WHEN sender_id=? THEN recipient_id ELSE sender_id END)
            ORDER BY m.id DESC LIMIT ?""",
            (employee_id, employee_id, employee_id, employee_id, max(1,min(int(limit),100)))).fetchall()
    return [dict(row) for row in rows]
