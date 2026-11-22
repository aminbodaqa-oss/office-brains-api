from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from database import _connect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_platform_billing_db() -> None:
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_plans (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            monthly_price_minor INTEGER NOT NULL DEFAULT 0 CHECK(monthly_price_minor >= 0),
            yearly_price_minor INTEGER NOT NULL DEFAULT 0 CHECK(yearly_price_minor >= 0),
            currency TEXT NOT NULL DEFAULT 'EGP',
            limits_json TEXT NOT NULL DEFAULT '{}',
            active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0,1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_subscriptions (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL REFERENCES platform_customers(id) ON DELETE CASCADE,
            plan_code TEXT NOT NULL REFERENCES platform_plans(code),
            billing_cycle TEXT NOT NULL CHECK(billing_cycle IN ('monthly','yearly')),
            status TEXT NOT NULL CHECK(status IN ('pending_payment','active','past_due','cancelled','expired')),
            payment_status TEXT NOT NULL CHECK(payment_status IN ('unpaid','paid','refunded')),
            amount_minor INTEGER NOT NULL CHECK(amount_minor >= 0),
            currency TEXT NOT NULL DEFAULT 'EGP',
            starts_at TEXT NOT NULL,
            ends_at TEXT NOT NULL,
            paid_at TEXT,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_platform_subscriptions_customer ON platform_subscriptions(customer_id,created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_platform_subscriptions_status ON platform_subscriptions(status,ends_at)")
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_billing_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscription_id TEXT NOT NULL REFERENCES platform_subscriptions(id) ON DELETE CASCADE,
            actor TEXT NOT NULL,
            event_type TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )""")
        defaults = [
            ("trial", "تجريبية", "باقة تجريبية لفترة محدودة"),
            ("starter", "بداية", "للأعمال الناشئة"),
            ("professional", "احترافية", "للأعمال النامية"),
            ("business", "أعمال", "لفرق العمل والشركات"),
            ("enterprise", "مؤسسات", "حلول مخصصة للمؤسسات"),
        ]
        for code, name, description in defaults:
            conn.execute(
                """INSERT OR IGNORE INTO platform_plans
                   (code,name,description,monthly_price_minor,yearly_price_minor,currency,limits_json,active,created_at,updated_at)
                   VALUES(?,?,?,0,0,'EGP','{}',0,?,?)""",
                (code, name, description, _now(), _now()),
            )


def expire_due_platform_subscriptions() -> int:
    """Mark elapsed paid subscriptions expired and suspend customers with no remaining coverage."""
    now = _now()
    with _connect() as conn:
        due = conn.execute(
            """SELECT id,customer_id FROM platform_subscriptions
               WHERE status='active' AND ends_at<=?""", (now,)
        ).fetchall()
        for item in due:
            conn.execute(
                "UPDATE platform_subscriptions SET status='expired',updated_at=? WHERE id=?",
                (now, item["id"]),
            )
            replacement = conn.execute(
                """SELECT plan_code FROM platform_subscriptions
                   WHERE customer_id=? AND id<>? AND status='active'
                     AND payment_status='paid' AND ends_at>? ORDER BY ends_at DESC LIMIT 1""",
                (item["customer_id"], item["id"], now),
            ).fetchone()
            if replacement:
                conn.execute(
                    "UPDATE platform_customers SET plan_code=?,status='active',updated_at=? WHERE id=?",
                    (replacement["plan_code"], now, item["customer_id"]),
                )
                conn.execute(
                    "UPDATE platform_workspaces SET status='active',updated_at=? WHERE customer_id=?",
                    (now, item["customer_id"]),
                )
            else:
                conn.execute(
                    "UPDATE platform_customers SET status='suspended',updated_at=? WHERE id=?",
                    (now, item["customer_id"]),
                )
                conn.execute(
                    "UPDATE platform_workspaces SET status='suspended',updated_at=? WHERE customer_id=?",
                    (now, item["customer_id"]),
                )
    return len(due)


def _plan(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["limits"] = json.loads(item.pop("limits_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        item["limits"] = {}
    item["active"] = bool(item["active"])
    return item


def list_platform_plans(include_inactive: bool = True) -> dict[str, Any]:
    with _connect() as conn:
        where = "" if include_inactive else "WHERE active=1"
        rows = conn.execute(f"SELECT * FROM platform_plans {where} ORDER BY CASE code WHEN 'trial' THEN 0 WHEN 'starter' THEN 1 WHEN 'professional' THEN 2 WHEN 'business' THEN 3 ELSE 4 END").fetchall()
    return {"plans": [_plan(row) for row in rows], "currency": "EGP"}


def save_platform_plan(code: str, name: str, description: str,
                       monthly_price_minor: int, yearly_price_minor: int,
                       limits: dict[str, Any], active: bool, actor: str) -> dict[str, Any]:
    code = code.strip().lower()
    name = name.strip()
    if not code or len(code) > 40 or not code.replace("_", "").isalnum():
        raise ValueError("كود الباقة غير صحيح.")
    if not name or len(name) > 100:
        raise ValueError("اسم الباقة مطلوب وبحد أقصى 100 حرف.")
    if not isinstance(limits, dict) or len(json.dumps(limits, ensure_ascii=False)) > 8000:
        raise ValueError("حدود الباقة غير صالحة.")
    for value in (monthly_price_minor, yearly_price_minor):
        if int(value) < 0 or int(value) > 1000000000:
            raise ValueError("السعر خارج النطاق المسموح.")
    now = _now()
    with _connect() as conn:
        exists = conn.execute("SELECT code FROM platform_plans WHERE code=?", (code,)).fetchone()
        if exists:
            conn.execute("""UPDATE platform_plans SET name=?,description=?,monthly_price_minor=?,
                yearly_price_minor=?,limits_json=?,active=?,updated_at=? WHERE code=?""",
                (name, description[:1000], int(monthly_price_minor), int(yearly_price_minor),
                 json.dumps(limits, ensure_ascii=False), int(active), now, code))
        else:
            conn.execute("""INSERT INTO platform_plans
                (code,name,description,monthly_price_minor,yearly_price_minor,currency,limits_json,active,created_at,updated_at)
                VALUES(?,?,?,?,?,'EGP',?,?,?,?)""",
                (code, name, description[:1000], int(monthly_price_minor), int(yearly_price_minor),
                 json.dumps(limits, ensure_ascii=False), int(active), now, now))
        conn.execute("""INSERT INTO platform_audit_log(actor,action,entity_type,entity_id,created_at)
            VALUES(?,?,?,?,?)""", (actor, "plan_saved", "plan", code, now))
        row = conn.execute("SELECT * FROM platform_plans WHERE code=?", (code,)).fetchone()
    return _plan(row)


def list_platform_subscriptions(customer_id: str = "", status: str = "") -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []
    if customer_id:
        clauses.append("s.customer_id=?")
        params.append(customer_id)
    if status in {"pending_payment", "active", "past_due", "cancelled", "expired"}:
        clauses.append("s.status=?")
        params.append(status)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(f"""SELECT s.*,c.company_name,c.email,p.name AS plan_name
            FROM platform_subscriptions s
            JOIN platform_customers c ON c.id=s.customer_id
            JOIN platform_plans p ON p.code=s.plan_code
            {where} ORDER BY s.created_at DESC LIMIT 300""", params).fetchall()
        totals = {str(r["status"]): int(r["total"]) for r in conn.execute(
            "SELECT status,COUNT(*) AS total FROM platform_subscriptions GROUP BY status").fetchall()}
    return {"subscriptions": [dict(row) for row in rows],
            "totals": {"all": sum(totals.values()), **totals}}


def create_platform_subscription(customer_id: str, plan_code: str, billing_cycle: str,
                                 starts_at: str | None, notes: str, actor: str) -> dict[str, Any]:
    if billing_cycle not in {"monthly", "yearly"}:
        raise ValueError("دورة الفوترة غير صحيحة.")
    now_dt = datetime.now(timezone.utc)
    try:
        start_dt = datetime.fromisoformat(starts_at.replace("Z", "+00:00")) if starts_at else now_dt
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        raise ValueError("تاريخ بداية الاشتراك غير صحيح.")
    if start_dt > now_dt:
        raise ValueError("تاريخ بداية الاشتراك لا يمكن أن يكون في المستقبل حاليًا.")
    with _connect() as conn:
        customer = conn.execute("SELECT id FROM platform_customers WHERE id=?", (customer_id,)).fetchone()
        plan = conn.execute("SELECT * FROM platform_plans WHERE code=? AND active=1", (plan_code,)).fetchone()
        if not customer:
            raise ValueError("العميل غير موجود.")
        if not plan:
            raise ValueError("الباقة غير موجودة أو غير مفعّلة.")
        price = int(plan["monthly_price_minor"] if billing_cycle == "monthly" else plan["yearly_price_minor"])
        duration = 30 if billing_cycle == "monthly" else 365
        end_dt = start_dt + timedelta(days=duration)
        now = _now()
        sub_id = str(uuid.uuid4())
        conn.execute("""INSERT INTO platform_subscriptions
            (id,customer_id,plan_code,billing_cycle,status,payment_status,amount_minor,currency,
             starts_at,ends_at,notes,created_at,updated_at)
            VALUES(?,?,?,?,'pending_payment','unpaid',?,'EGP',?,?,?,?,?)""",
            (sub_id, customer_id, plan_code, billing_cycle, price, start_dt.isoformat(),
             end_dt.isoformat(), notes[:2000], now, now))
        conn.execute("""INSERT INTO platform_billing_events(subscription_id,actor,event_type,details,created_at)
            VALUES(?,?, 'subscription_created', ?, ?)""", (sub_id, actor, "بانتظار تأكيد الدفع اليدوي", now))
        row = conn.execute("SELECT * FROM platform_subscriptions WHERE id=?", (sub_id,)).fetchone()
    return dict(row)


def update_platform_subscription(subscription_id: str, payment_status: str | None,
                                 status: str | None, notes: str | None,
                                 actor: str) -> dict[str, Any] | None:
    allowed_payment = {"unpaid", "paid", "refunded"}
    allowed_status = {"pending_payment", "active", "past_due", "cancelled", "expired"}
    if payment_status is not None and payment_status not in allowed_payment:
        raise ValueError("حالة الدفع غير صحيحة.")
    if status is not None and status not in allowed_status:
        raise ValueError("حالة الاشتراك غير صحيحة.")
    now = _now()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM platform_subscriptions WHERE id=?", (subscription_id,)).fetchone()
        if not row:
            return None
        next_payment = payment_status or str(row["payment_status"])
        next_status = status or str(row["status"])
        if next_payment == "paid" and next_status == "pending_payment":
            next_status = "active"
        elif next_payment != "paid" and next_status == "active":
            next_status = "pending_payment"
        if next_payment == "refunded":
            next_status = "cancelled"
        paid_at = now if next_payment == "paid" and not row["paid_at"] else row["paid_at"]
        conn.execute("""UPDATE platform_subscriptions SET payment_status=?,status=?,notes=?,paid_at=?,updated_at=?
            WHERE id=?""", (next_payment, next_status, notes if notes is not None else row["notes"],
                             paid_at, now, subscription_id))
        if next_status == "active" and next_payment == "paid":
            conn.execute("""UPDATE platform_customers SET plan_code=?,status='active',updated_at=? WHERE id=?""",
                         (row["plan_code"], now, row["customer_id"]))
            conn.execute("""UPDATE platform_workspaces SET status='active',updated_at=? WHERE customer_id=?""",
                         (now, row["customer_id"]))
        elif next_status == "pending_payment" and next_payment != "paid":
            replacement = conn.execute(
                """SELECT plan_code FROM platform_subscriptions
                   WHERE customer_id=? AND id<>? AND status='active' AND payment_status='paid'
                     AND ends_at>=? ORDER BY ends_at DESC LIMIT 1""",
                (row["customer_id"], subscription_id, now),
            ).fetchone()
            customer_status = "active" if replacement else "suspended"
            if replacement:
                conn.execute("UPDATE platform_customers SET plan_code=?,status='active',updated_at=? WHERE id=?",
                             (replacement["plan_code"], now, row["customer_id"]))
            else:
                conn.execute("UPDATE platform_customers SET status='suspended',updated_at=? WHERE id=?",
                             (now, row["customer_id"]))
            conn.execute("UPDATE platform_workspaces SET status=?,updated_at=? WHERE customer_id=?",
                         (customer_status, now, row["customer_id"]))
        elif next_status in {"cancelled", "expired", "past_due"}:
            replacement = conn.execute(
                """SELECT plan_code FROM platform_subscriptions
                   WHERE customer_id=? AND id<>? AND status='active' AND payment_status='paid'
                     AND ends_at>=? ORDER BY ends_at DESC LIMIT 1""",
                (row["customer_id"], subscription_id, now),
            ).fetchone()
            customer_status = "active" if replacement or next_status == "past_due" else "suspended"
            if replacement:
                conn.execute("UPDATE platform_customers SET plan_code=?,status='active',updated_at=? WHERE id=?",
                             (replacement["plan_code"], now, row["customer_id"]))
            else:
                conn.execute("UPDATE platform_customers SET status=?,updated_at=? WHERE id=?",
                             (customer_status, now, row["customer_id"]))
            conn.execute("UPDATE platform_workspaces SET status=?,updated_at=? WHERE customer_id=?",
                         (customer_status, now, row["customer_id"]))
        conn.execute("""INSERT INTO platform_billing_events(subscription_id,actor,event_type,details,created_at)
            VALUES(?,?,?,?,?)""", (subscription_id, actor, "subscription_updated",
                                    f"payment={next_payment}; status={next_status}", now))
        conn.execute("""INSERT INTO platform_audit_log(actor,action,entity_type,entity_id,created_at)
            VALUES(?,?,?,?,?)""", (actor, "subscription_updated", "subscription", subscription_id, now))
        updated = conn.execute("SELECT * FROM platform_subscriptions WHERE id=?", (subscription_id,)).fetchone()
    return dict(updated)
