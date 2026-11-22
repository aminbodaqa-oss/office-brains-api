# Tenant isolation audit and implementation gate

## Current state

The platform customer registry is present, but it is not yet a multi-tenant application. A customer row and a workspace row are created together; there is no customer user, membership, workspace-scoped session, or tenant-aware data access layer. The existing office login authenticates only the configured platform owner.

**Release rule:** do not issue customer credentials, expose the office APIs to customer users, or advertise customer workspaces as operational until every tenant-owned read/write path and background worker is scoped and the cross-tenant tests pass.

## Data inventory

The current SQLite-backed application contains the following data families. Names below are the current table names created by the codebase.

| Data family | Tables | Required boundary |
|---|---|---|
| Conversations and employee memory | `interactions`, `memories` | workspace |
| Work management | `tasks`, `task_executions`, `task_delegation_plans`, `task_delegation_diagnostics`, `task_delegation_reports` | workspace; child rows inherit and must match their parent task |
| Meetings and activity | `meetings`, `activity_log` | workspace |
| Internal employee messaging | `internal_messages`, `office_whatsapp_messages` | workspace |
| Autonomous operations | `autonomous_runs`, `autonomous_reports` | workspace; run uniqueness must become (workspace_id, run_date) |
| Notifications and delivery | `notifications`, `push_devices`, `push_outbox` | workspace; a device and its queued deliveries must never cross workspaces |
| Authentication | `auth_sessions`, `owner_credentials` | owner auth remains platform-only; customer credentials and sessions need a separate tenant identity model |
| Platform control plane | `platform_customers`, `platform_workspaces`, `platform_audit_log` | platform-admin only; never expose as tenant data |

The employee catalogue is currently a shared Python constant, not tenant-owned data. Before customer workspaces are enabled, each workspace needs its own employee roster/configuration and its own company context, AI/provider configuration, integrations, schedules, and secrets. Environment-level credentials must not silently become shared customer credentials.

## Security invariants

1. Resolve the workspace from a verified server-side membership/session. Never accept a client-supplied `workspace_id` as authority.
2. A tenant principal carries immutable `user_id`, `workspace_id`, role, and account status claims. A suspended customer/workspace or disabled membership is denied on every request.
3. Every tenant-owned SELECT, INSERT, UPDATE, and DELETE is scoped by the resolved workspace. Updates/deletes must include both the record ID and workspace ID in the predicate.
4. Related records are checked through their parent in the same workspace. A task execution, delegation plan, report, or diagnostic cannot be attached to another workspace's task.
5. Background workers claim work by workspace and carry that workspace context through AI calls, notifications, internal messages, retries, and final reports. A global worker must not accidentally process tenant work using the platform owner's employee roster or context.
6. Push tokens, queued pushes, files, integration credentials, and scheduled jobs are workspace-owned. No cross-workspace broadcast or storage-path reuse.
7. Platform-admin APIs remain a separate audience and authorization boundary. Platform admins may administer customer metadata; tenant APIs must not accept platform tokens as tenant sessions.
8. Preserve the existing owner workspace and all existing records. No destructive migration, blanket reassignment, or live data rewrite without a verified backup, row-count checks, and rollback plan.

## Safe implementation sequence

### Phase A — foundation (no tenant access yet)
- Add tenant identity and membership tables with unique normalized email, password hash, role, status, and workspace foreign key.
- Add tenant token issuance/verification with a distinct audience and signing secret; leave owner auth unchanged.
- Add a server-side tenant principal dependency that checks current membership and customer/workspace status on each request.
- Add migration metadata and a dry-run schema/data audit. Do not enable customer login.

### Phase B — data ownership migration
- Introduce a reserved owner workspace and explicitly map all existing owner data to it.
- Add `workspace_id` to every tenant-owned table and the necessary indexes.
- Backfill existing rows transactionally; verify every row has exactly one valid workspace.
- Add workspace-aware uniqueness constraints where current global uniqueness would collide across customers.
- Keep platform-only tables outside tenant scoping.

### Phase C — repository and API enforcement
- Change repository functions to require workspace context; avoid optional workspace arguments that default to global access.
- Scope all office endpoints, including nested IDs and bulk actions.
- Add workspace-aware employee configuration, files, integrations, provider settings, notifications, and schedules.
- Keep platform-owner endpoints separate and explicit.

### Phase D — background execution
- Scope task claiming, automation runs, reports, delegation, push delivery, retries, and notifications by workspace.
- Ensure AI prompts and retrieved context only include the active workspace's data.
- Ensure tenant jobs cannot use owner-only external integrations or secrets unless explicitly configured for that workspace.

### Phase E — tests and controlled enablement
- Create two test workspaces and prove that A cannot list/read/update/delete B's tasks, chats, memories, meetings, messages, notifications, devices, files, or executions.
- Test forged workspace IDs, nested-resource ID substitution, suspended customers, disabled users, expired/wrong-audience tokens, and background-job isolation.
- Verify owner login and existing owner records still work unchanged.
- Only then enable invitations/customer login and expose the customer workspace URL.

## Known high-risk paths found in the current implementation

- `workflow.py` performs task and related-record queries using numeric IDs without a workspace predicate.
- `database.py` reads and mutates conversations, memories, notifications, push devices, and sessions globally.
- `internal_messaging.py` and `office_whatsapp.py` address employees globally by employee ID.
- `automation.py` uses a single global daily run key and shared employee/context lists.
- `task_runner.py` claims from one global execution queue and builds prompts from the shared employee catalogue.
- `main.py` currently protects office endpoints with the owner-only dependency; tenant authorization is not present.

These are not isolated UI changes. They require coordinated repository, API, migration, and worker changes. The existing owner flow must remain the compatibility baseline throughout.
