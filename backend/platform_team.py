from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from database import _connect
from employees import EMPLOYEES


def init_platform_team_db() -> None:
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_employee_overrides (
            employee_id TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            department TEXT NOT NULL,
            instructions TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")


def _base(employee_id: str) -> dict[str, Any] | None:
    item = next((employee for employee in EMPLOYEES if employee.get("id") == employee_id), None)
    return dict(item) if item else None


def get_platform_employee_profile(employee_id: str) -> dict[str, Any] | None:
    profile = _base(employee_id)
    if not profile:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT role,department,instructions FROM platform_employee_overrides WHERE employee_id=?",
            (employee_id,),
        ).fetchone()
    profile["additional_instructions"] = ""
    if row:
        profile["role"] = row["role"]
        profile["department"] = row["department"]
        profile["additional_instructions"] = row["instructions"]
        if row["instructions"]:
            base_instructions = profile.get("instructions", "")
            profile["instructions"] = (
                base_instructions
                + "\n\nتعليمات إضافية معتمدة من مالك المنصة:\n"
                + row["instructions"]
            )
    return profile


def list_platform_team() -> list[dict[str, Any]]:
    return [get_platform_employee_profile(str(employee["id"])) for employee in EMPLOYEES]


def save_platform_employee_profile(employee_id: str, role: str, department: str,
                                   instructions: str, actor: str) -> dict[str, Any] | None:
    if not _base(employee_id):
        return None
    role, department, instructions = role.strip(), department.strip(), instructions.strip()
    if not role or len(role) > 160:
        raise ValueError("المسمى الوظيفي مطلوب وبحد أقصى 160 حرفًا.")
    if not department or len(department) > 160:
        raise ValueError("القسم مطلوب وبحد أقصى 160 حرفًا.")
    if len(instructions) > 6000:
        raise ValueError("التعليمات الإضافية يجب ألا تتجاوز 6000 حرف.")
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("""INSERT INTO platform_employee_overrides
            (employee_id,role,department,instructions,updated_by,updated_at)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(employee_id) DO UPDATE SET role=excluded.role,
            department=excluded.department,instructions=excluded.instructions,
            updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
            (employee_id, role, department, instructions, actor, now))
        conn.execute("""INSERT INTO platform_audit_log(actor,action,entity_type,entity_id,created_at)
            VALUES(?,?,?,?,?)""",
            (actor, "platform_employee_profile_updated", "employee", employee_id, now))
    return get_platform_employee_profile(employee_id)
