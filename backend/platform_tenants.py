from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from database import DB_PATH, _connect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_platform_tenants_db() -> None:
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_customers (
            id TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            contact_name TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL COLLATE NOCASE,
            phone TEXT NOT NULL DEFAULT '',
            plan_code TEXT NOT NULL DEFAULT 'trial',
            status TEXT NOT NULL DEFAULT 'trial' CHECK(status IN ('trial','active','suspended')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_platform_customers_email ON platform_customers(email)")
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_workspaces (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL UNIQUE REFERENCES platform_customers(id) ON DELETE CASCADE,
            workspace_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'trial' CHECK(status IN ('trial','active','suspended')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_platform_workspaces_customer ON platform_workspaces(customer_id)")
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_platform_audit_created ON platform_audit_log(created_at DESC)")


def list_platform_customers(query: str = "", status: str = "", limit: int = 100) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []
    if query.strip():
        term = f"%{query.strip()[:120]}%"
        clauses.append("(c.company_name LIKE ? OR c.contact_name LIKE ? OR c.email LIKE ? OR c.phone LIKE ?)")
        params.extend([term, term, term, term])
    if status in {"trial", "active", "suspended"}:
        clauses.append("c.status=?")
        params.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(f"""SELECT c.id,c.company_name,c.contact_name,c.email,c.phone,c.plan_code,
            c.status,c.created_at,c.updated_at,w.id AS workspace_id,w.workspace_name,
            w.status AS workspace_status
            FROM platform_customers c LEFT JOIN platform_workspaces w ON w.customer_id=c.id
            {where} ORDER BY c.created_at DESC LIMIT ?""", (*params, max(1, min(int(limit), 200)))).fetchall()
        totals = {str(row["status"]): int(row["total"]) for row in conn.execute(
            "SELECT status,COUNT(*) AS total FROM platform_customers GROUP BY status").fetchall()}
    return {"customers": [dict(row) for row in rows],
            "totals": {"all": sum(totals.values()), "trial": totals.get("trial", 0),
                       "active": totals.get("active", 0), "suspended": totals.get("suspended", 0)}}


def create_platform_customer(company_name: str, contact_name: str, email: str,
                             phone: str, plan_code: str, actor: str) -> dict[str, Any]:
    company_name = company_name.strip()
    email = email.strip().lower()
    if not company_name or not email or "@" not in email or len(email) > 254:
        raise ValueError("اسم الشركة والبريد الإلكتروني الصحيح مطلوبان.")
    if plan_code not in {"trial", "starter", "professional", "business", "enterprise"}:
        raise ValueError("الباقة المحددة غير معروفة.")
    customer_id = str(uuid.uuid4())
    workspace_id = str(uuid.uuid4())
    now = _now()
    status = "trial" if plan_code == "trial" else "active"
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("""INSERT INTO platform_customers
                (id,company_name,contact_name,email,phone,plan_code,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (customer_id, company_name, contact_name.strip(), email, phone.strip(),
                 plan_code, status, now, now))
            conn.execute("""INSERT INTO platform_workspaces
                (id,customer_id,workspace_name,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?)""",
                (workspace_id, customer_id, company_name, status, now, now))
            conn.execute("""INSERT INTO platform_audit_log(actor,action,entity_type,entity_id,created_at)
                VALUES(?,?,?,?,?)""", (actor, "customer_created", "customer", customer_id, now))
    except sqlite3.IntegrityError as exc:
        if "email" in str(exc).lower() or "unique" in str(exc).lower():
            raise ValueError("البريد الإلكتروني مسجل بالفعل.") from exc
        raise
    return {"id": customer_id, "workspace_id": workspace_id, "company_name": company_name,
            "email": email, "plan_code": plan_code, "status": status}


def update_platform_customer(customer_id: str, status: str | None, plan_code: str | None,
                             actor: str) -> dict[str, Any] | None:
    if status is not None and status not in {"trial", "active", "suspended"}:
        raise ValueError("حالة الحساب غير صحيحة.")
    if plan_code is not None and plan_code not in {"trial", "starter", "professional", "business", "enterprise"}:
        raise ValueError("الباقة المحددة غير معروفة.")
    now = _now()
    with _connect() as conn:
        row = conn.execute("SELECT id,status,plan_code FROM platform_customers WHERE id=?", (customer_id,)).fetchone()
        if not row:
            return None
        next_status = status or str(row["status"])
        next_plan = plan_code or str(row["plan_code"])
        conn.execute("UPDATE platform_customers SET status=?,plan_code=?,updated_at=? WHERE id=?",
                     (next_status, next_plan, now, customer_id))
        conn.execute("UPDATE platform_workspaces SET status=?,updated_at=? WHERE customer_id=?",
                     (next_status, now, customer_id))
        conn.execute("""INSERT INTO platform_audit_log(actor,action,entity_type,entity_id,created_at)
            VALUES(?,?,?,?,?)""", (actor, "customer_updated", "customer", customer_id, now))
        return {"id": customer_id, "status": next_status, "plan_code": next_plan}
