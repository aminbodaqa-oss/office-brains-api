from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from database import _connect

TASK_STATUSES = {"open", "in_progress", "review", "completed", "cancelled"}
TASK_PRIORITIES = {"low", "normal", "high", "urgent"}
EXECUTION_STATUSES = {"queued", "running", "review", "failed", "completed", "cancelled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_workflow_db() -> None:
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            assigned_to TEXT NOT NULL,
            created_by TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            priority TEXT NOT NULL DEFAULT 'normal',
            due_at TEXT,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_due ON tasks(status,due_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assigned_to,status)")
        conn.execute("""CREATE TABLE IF NOT EXISTS task_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL UNIQUE,
            employee_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            result TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '',
            attempts INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_task_executions_queue ON task_executions(status,created_at)")
        conn.execute("""CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            agenda TEXT NOT NULL DEFAULT '',
            attendees TEXT NOT NULL DEFAULT '[]',
            scheduled_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'scheduled',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            minutes TEXT NOT NULL DEFAULT ''
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meetings_scheduled ON meetings(scheduled_at,status)")
        conn.execute("""CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            summary TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at DESC)")


def log_activity(actor: str, action: str, entity_type: str, entity_id: int | None,
                 summary: str, details: str = "") -> int:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO activity_log(actor,action,entity_type,entity_id,summary,details,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (actor[:120], action[:40], entity_type[:40], entity_id, summary[:500], details[:12000], _now()),
        )
        return int(cur.lastrowid)


def list_tasks(limit: int = 100, status: str | None = None, assigned_to: str | None = None) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    clauses, params = [], []
    if status:
        clauses.append("t.status=?")
        params.append(status)
    if assigned_to:
        clauses.append("t.assigned_to=?")
        params.append(assigned_to)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT t.*, e.status AS execution_status, e.result AS execution_result,
                      e.error AS execution_error, e.attempts AS execution_attempts,
                      e.started_at AS execution_started_at, e.finished_at AS execution_finished_at
               FROM tasks t LEFT JOIN task_executions e ON e.task_id=t.id"""
            + where +
            """ ORDER BY CASE t.status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 WHEN 'review' THEN 2 ELSE 3 END,
                      CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
                      COALESCE(t.due_at,'9999'), t.id DESC LIMIT ?""",
            (*params, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def create_task(title: str, description: str, assigned_to: str, created_by: str,
                priority: str = "normal", due_at: str | None = None, source: str = "manual") -> dict[str, Any]:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO tasks(title,description,assigned_to,created_by,status,priority,due_at,source,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (title.strip()[:180], description[:5000], assigned_to, created_by, "open", priority,
             due_at, source[:40], now, now),
        )
        task_id = int(cur.lastrowid)
        conn.execute(
            """INSERT INTO task_executions(task_id,employee_id,status,created_at,updated_at)
               VALUES(?,?,'queued',?,?)""",
            (task_id, assigned_to, now, now),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    log_activity(created_by, "task_created", "task", task_id,
                 f"تم إنشاء مهمة جديدة وتكليف {assigned_to}: {title[:150]}", description)
    log_activity("النظام", "task_queued", "task", task_id,
                 f"تم وضع المهمة #{task_id} في طابور التنفيذ", "الموظف المسؤول: " + assigned_to)
    return dict(row)


def update_task(task_id: int, updates: dict[str, Any], actor: str) -> dict[str, Any] | None:
    allowed = {"title", "description", "assigned_to", "status", "priority", "due_at"}
    clean = {key: value for key, value in updates.items() if key in allowed}
    if not clean:
        return None
    now = _now()
    clean["updated_at"] = now
    if clean.get("status") == "completed":
        clean["completed_at"] = now
    elif clean.get("status") in {"open", "in_progress", "review"}:
        clean["completed_at"] = None
    columns = list(clean)
    sql = "UPDATE tasks SET " + ",".join(f"{column}=?" for column in columns) + " WHERE id=?"
    with _connect() as conn:
        before = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if before is None:
            return None
        conn.execute(sql, [clean[column] for column in columns] + [task_id])
        if clean.get("status") in {"completed", "cancelled"}:
            conn.execute(
                "UPDATE task_executions SET status=?,updated_at=?,finished_at=? WHERE task_id=?",
                (clean["status"], now, now, task_id),
            )
        elif "assigned_to" in clean or clean.get("status") == "open":
            assigned_to = clean.get("assigned_to", before["assigned_to"])
            conn.execute(
                """INSERT INTO task_executions(task_id,employee_id,status,result,error,attempts,created_at,updated_at,started_at,finished_at)
                   VALUES(?,?,'queued','','',0,?,?,NULL,NULL)
                   ON CONFLICT(task_id) DO UPDATE SET employee_id=excluded.employee_id,status='queued',
                   result='',error='',attempts=0,updated_at=excluded.updated_at,started_at=NULL,finished_at=NULL""",
                (task_id, assigned_to, now, now),
            )
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    changed = ", ".join(f"{key}: {before[key]!s} ← {clean[key]!s}" for key in columns if key not in {"updated_at", "completed_at"})
    log_activity(actor, "task_updated", "task", task_id, f"تم تحديث المهمة #{task_id}", changed)
    return dict(row)


def claim_next_task_execution() -> dict[str, Any] | None:
    now = _now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT t.*, e.id AS execution_id, e.attempts AS execution_attempts
               FROM task_executions e JOIN tasks t ON t.id=e.task_id
               WHERE e.status='queued' AND t.status NOT IN ('completed','cancelled')
               ORDER BY CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
                        e.created_at ASC, e.id ASC LIMIT 1"""
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE task_executions SET status='running',attempts=attempts+1,started_at=?,updated_at=?,error='' WHERE id=? AND status='queued'",
            (now, now, row["execution_id"]),
        )
        conn.execute("UPDATE tasks SET status='in_progress',updated_at=? WHERE id=?", (now, row["id"]))
        claimed = conn.execute(
            """SELECT t.*, e.id AS execution_id, e.attempts AS execution_attempts
               FROM task_executions e JOIN tasks t ON t.id=e.task_id WHERE e.id=?""",
            (row["execution_id"],),
        ).fetchone()
    return dict(claimed) if claimed else None


def finish_task_execution(task_id: int, result: str, actor: str) -> dict[str, Any] | None:
    now = _now()
    with _connect() as conn:
        execution = conn.execute("SELECT * FROM task_executions WHERE task_id=?", (task_id,)).fetchone()
        if execution is None or execution["status"] != "running":
            return None
        conn.execute(
            "UPDATE task_executions SET status='review',result=?,error='',updated_at=?,finished_at=? WHERE task_id=?",
            (result[:20000], now, now, task_id),
        )
        conn.execute("UPDATE tasks SET status='review',updated_at=? WHERE id=?", (now, task_id))
        task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    log_activity(actor, "task_result_ready", "task", task_id,
                 f"الموظف {execution['employee_id']} سلّم نتيجة المهمة #{task_id} للمراجعة", result[:12000])
    return dict(task) if task else None


def fail_task_execution(task_id: int, error: str, actor: str) -> dict[str, Any] | None:
    now = _now()
    with _connect() as conn:
        execution = conn.execute("SELECT * FROM task_executions WHERE task_id=?", (task_id,)).fetchone()
        if execution is None or execution["status"] != "running":
            return None
        conn.execute(
            "UPDATE task_executions SET status='failed',error=?,updated_at=?,finished_at=? WHERE task_id=?",
            (error[:5000], now, now, task_id),
        )
        conn.execute("UPDATE tasks SET status='open',updated_at=? WHERE id=?", (now, task_id))
        task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    log_activity(actor, "task_execution_failed", "task", task_id,
                 f"تعذر تنفيذ المهمة #{task_id}", error[:12000])
    return dict(task) if task else None


def retry_task_execution(task_id: int) -> bool:
    now = _now()
    with _connect() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if task is None or task["status"] in {"completed", "cancelled"}:
            return False
        cur = conn.execute(
            """UPDATE task_executions SET status='queued',result='',error='',attempts=0,
               updated_at=?,started_at=NULL,finished_at=NULL WHERE task_id=? AND status='failed'""",
            (now, task_id),
        )
        if cur.rowcount:
            conn.execute("UPDATE tasks SET status='open',updated_at=? WHERE id=?", (now, task_id))
    if cur.rowcount:
        log_activity("الريّس", "task_requeued", "task", task_id, f"تمت إعادة وضع المهمة #{task_id} في طابور التنفيذ")
    return bool(cur.rowcount)


def get_task_execution(task_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM task_executions WHERE task_id=?", (task_id,)).fetchone()
    return dict(row) if row else None


def list_meetings(limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM meetings ORDER BY scheduled_at DESC,id DESC LIMIT ?", (limit,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["attendees"] = json.loads(item["attendees"])
        except (TypeError, json.JSONDecodeError):
            item["attendees"] = []
        result.append(item)
    return result


def create_meeting(title: str, agenda: str, attendees: list[str], scheduled_at: str, created_by: str) -> dict[str, Any]:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO meetings(title,agenda,attendees,scheduled_at,status,created_by,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (title[:180], agenda[:5000], json.dumps(attendees, ensure_ascii=False), scheduled_at, "scheduled", created_by, now),
        )
        meeting_id = int(cur.lastrowid)
        row = conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
    item = dict(row)
    item["attendees"] = attendees
    log_activity(created_by, "meeting_scheduled", "meeting", meeting_id,
                 f"تمت جدولة اجتماع: {title}", "الموعد: " + scheduled_at + "\nالحضور: " + "، ".join(attendees) + "\n" + agenda)
    return item


def update_meeting(meeting_id: int, updates: dict[str, Any], actor: str) -> dict[str, Any] | None:
    allowed = {"status", "minutes"}
    clean = {key: value for key, value in updates.items() if key in allowed}
    if not clean:
        return None
    if "minutes" in clean:
        clean["minutes"] = str(clean["minutes"])[:20000]
    columns = list(clean)
    with _connect() as conn:
        before = conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
        if before is None:
            return None
        conn.execute("UPDATE meetings SET " + ",".join(f"{column}=?" for column in columns) + " WHERE id=?",
                     [clean[column] for column in columns] + [meeting_id])
        row = conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
    log_activity(actor, "meeting_updated", "meeting", meeting_id,
                 f"تم تحديث الاجتماع #{meeting_id}", ", ".join(columns))
    item = dict(row)
    try:
        item["attendees"] = json.loads(item["attendees"])
    except (TypeError, json.JSONDecodeError):
        item["attendees"] = []
    return item


def list_activity(limit: int = 60) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 150))
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def workflow_overview() -> dict[str, Any]:
    with _connect() as conn:
        counts = conn.execute("SELECT status,COUNT(*) AS total FROM tasks GROUP BY status").fetchall()
        total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        upcoming = conn.execute(
            "SELECT COUNT(*) FROM meetings WHERE status='scheduled' AND scheduled_at>=?",
            (_now(),),
        ).fetchone()[0]
        overdue = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status NOT IN ('completed','cancelled') AND due_at IS NOT NULL AND due_at < ?",
            (_now(),),
        ).fetchone()[0]
    return {
        "task_counts": {row["status"]: int(row["total"]) for row in counts},
        "tasks_total": int(total),
        "upcoming_meetings": int(upcoming),
        "overdue_tasks": int(overdue),
        "tasks": list_tasks(30),
        "meetings": list_meetings(10),
        "activity": list_activity(30),
    }
