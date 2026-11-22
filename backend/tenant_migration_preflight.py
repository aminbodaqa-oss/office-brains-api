from __future__ import annotations

from typing import Any

from database import _connect


# Business data that must belong to exactly one workspace before tenant access is enabled.
TENANT_DATA_TABLES: dict[str, str] = {
    "interactions": "conversations and employee context",
    "memories": "employee memories",
    "autonomous_runs": "automation run state",
    "autonomous_reports": "automation reports",
    "push_devices": "push device registrations",
    "push_outbox": "queued push deliveries",
    "notifications": "workspace notifications",
    "tasks": "tasks and assignments",
    "task_executions": "task execution state",
    "task_delegation_plans": "delegation plans",
    "task_delegation_diagnostics": "delegation diagnostics",
    "task_delegation_reports": "delegation reports",
    "meetings": "meetings and minutes",
    "activity_log": "workspace activity",
    "internal_messages": "internal employee messages",
    "office_whatsapp_messages": "office messaging history",
}

PLATFORM_TABLES = {
    "platform_customers",
    "platform_workspaces",
    "platform_audit_log",
    "tenant_users",
    "tenant_memberships",
    "owner_credentials",
    "auth_sessions",
}


def tenant_migration_preflight() -> dict[str, Any]:
    """Read-only inventory. This function deliberately performs no schema or data writes."""
    with _connect() as conn:
        existing = {
            str(row["name"])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        inventory: list[dict[str, Any]] = []
        missing_tables: list[str] = []
        missing_workspace_column: list[str] = []

        for table, purpose in TENANT_DATA_TABLES.items():
            if table not in existing:
                missing_tables.append(table)
                inventory.append({
                    "table": table,
                    "purpose": purpose,
                    "exists": False,
                    "rows": None,
                    "has_workspace_id": False,
                    "migration_status": "table_not_initialized",
                })
                continue

            columns = {
                str(row["name"])
                for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            }
            row_count = int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            has_workspace_id = "workspace_id" in columns
            if not has_workspace_id:
                missing_workspace_column.append(table)
            inventory.append({
                "table": table,
                "purpose": purpose,
                "exists": True,
                "rows": row_count,
                "has_workspace_id": has_workspace_id,
                "migration_status": "ready_for_workspace_backfill" if has_workspace_id else "needs_workspace_column",
            })

        identity_counts: dict[str, int] = {}
        for table in ("platform_customers", "platform_workspaces", "tenant_users", "tenant_memberships"):
            if table in existing:
                identity_counts[table] = int(
                    conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                )
            else:
                identity_counts[table] = 0

        foreign_key_issues: list[str] = []
        for table in ("platform_workspaces", "tenant_memberships"):
            if table in existing:
                violations = conn.execute(f'PRAGMA foreign_key_check("{table}")').fetchall()
                if violations:
                    foreign_key_issues.append(table)

    all_tenant_tables_ready = not missing_tables and not missing_workspace_column
    return {
        "mode": "read_only_preflight",
        "customer_access_enabled": False,
        "safe_to_run": True,
        "tenant_data_schema_ready": all_tenant_tables_ready,
        "summary": {
            "tenant_tables_expected": len(TENANT_DATA_TABLES),
            "tenant_tables_found": len(TENANT_DATA_TABLES) - len(missing_tables),
            "tables_missing_workspace_id": len(missing_workspace_column),
            "tables_not_initialized": len(missing_tables),
            "platform_foreign_key_issues": len(foreign_key_issues),
        },
        "identity_counts": identity_counts,
        "tables": inventory,
        "blockers": {
            "missing_tables": missing_tables,
            "missing_workspace_id": missing_workspace_column,
            "foreign_key_issues": foreign_key_issues,
        },
        "next_step": (
            "Create a verified backup, then prepare an explicit owner-workspace mapping and transactional migration."
            if not all_tenant_tables_ready or foreign_key_issues
            else "Review row counts and ownership mapping before any write migration."
        ),
        "guarantees": [
            "No table was created, altered, or dropped.",
            "No existing row was inserted, updated, or deleted.",
            "No customer login or tenant API was enabled.",
        ],
    }
