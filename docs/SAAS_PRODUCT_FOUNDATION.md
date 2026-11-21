# Office Brains — SaaS Product Foundation

Status: architecture baseline; no production behavior changed by this document.

## Product decision

Office Brains is an independent, web-first SaaS product. Vindora is to become one customer/workspace (or an explicitly isolated internal pilot), not the product identity, default company context, or a required integration.

The existing office login remains the customer workspace entry point during the migration. The platform owner's Super Admin entry must be separate, separately authorized, and never inferred from a normal workspace role.

## Repository audit — observed on 2026-11-22

- Backend: Python + FastAPI under `backend/`; static web app under `office/frontend/`; deployment docs describe GitHub Pages for the frontend and Bot Hosting for the API.
- Current owner authentication is single-owner: `OWNER_USERNAME`, password hash, and owner-only bearer dependency in `backend/auth.py` and `backend/main.py`.
- SQLite is the current persistence layer (`backend/database.py`, `DATABASE_PATH`); operational tables such as interactions, memories, notifications, sessions, tasks, executions, delegation plans/reports, meetings, and activity log have no tenant/workspace ownership column.
- Employee definitions and directory context are hardcoded in `backend/employees.py`.
- Vindora-specific coupling exists in `backend/vindora_client.py`, chat context assembly in `backend/main.py`, and frontend copy/configuration. For example, the current login view identifies VINDORA and the current browser app title is "مكتب Vindora الافتراضي".
- The frontend is split into HTML fragments and JavaScript modules loaded by `office/frontend/js/view-loader.js`; a legacy `office/js/` copy also exists. Any UI work must first confirm which copy is deployed and avoid editing both blindly.
- The repository tree inspected for this audit contains no `test/` directory. Regardless, the protected path rule remains: never create, modify, or delete anything under `test/`.
- No Super Admin console, public marketing website/CMS, tenant registration flow, subscription/billing module, or tenant isolation layer was found in the inspected tree.

## Target experience

### Public website
A separate public marketing surface with CMS-managed pages, sections, navigation, media, SEO metadata, pricing tables, FAQs, contact channels, and publication state. Content edits are drafts until explicitly published. Publishing must support preview, revision history, rollback, and audit events.

### Platform Super Admin
A separate protected route and authentication boundary for the platform owner/staff. Initial modules:
1. Command Center: platform health, active workspaces, subscription status, AI provider health, queue health, error trends, and cost/usage summaries.
2. Website Studio: section/page editor, media library, responsive preview, draft/publish workflow, revisions, rollback.
3. Workspaces/Customers: customer profile, workspace state, members, plan, usage, support status, and controlled suspension/reactivation.
4. Plans & Billing: plans, entitlements, usage limits, invoices/payment integration state; never trust client-side price or entitlement values.
5. AI Control: provider/model catalog, employee templates, tool catalog, budgets, safe defaults, and feature flags. Secrets stay server-side.
6. Operations: task queue, failed jobs, retries, notifications, integration health, audit log.
7. Platform settings: brand, locale, theme, public contact details, legal pages, email templates.

### Customer workspace
The existing office remains a distinct product surface for each customer. Workspace members, AI employees, conversations, memories, files, tasks, integrations, and notifications are scoped to that workspace. Workspace owners/admins do not receive platform Super Admin permissions.

## Target architecture boundaries

- Public Web: public routes and published CMS content only.
- Super Admin: platform-level administration, separate role and session audience.
- Workspace Web: current office experience, workspace-scoped session and API.
- API/Core: authentication, tenant context, policy enforcement, employee orchestration, task execution, memory, integrations, notifications.
- Data: relational records carry an immutable `workspace_id` where tenant-owned; platform-global records are explicitly classified as global. Use foreign keys and indexes for tenant scope.
- Background workers: every job carries workspace context and revalidates permissions/ownership before reading or writing tenant data.
- Integrations/secrets: encrypted server-side storage, per-workspace grants, revocation, and redacted logs.
- Billing/entitlements: server-side enforcement at API boundaries; usage events are metered independently from UI display.

## Security and data-isolation requirements

1. Never rely on a frontend-supplied `workspace_id` as authorization. Resolve workspace membership from the authenticated session/token.
2. Include workspace scope in every tenant-owned query, update, delete, task, notification, memory, file, and background job.
3. Separate platform-admin tokens from workspace tokens (distinct audience/claims and dependencies); add MFA for Super Admin before public launch.
4. Add role-based permissions for platform staff and workspace members; least privilege by default.
5. Record privileged changes in append-only audit events with actor, action, target, timestamp, and outcome.
6. Keep AI provider keys, payment secrets, signing keys, and integration credentials out of frontend bundles and logs.
7. Require explicit approval for external or consequential actions; use idempotency keys for payment and execution operations.
8. Add tenant-isolation tests before migrating any existing customer data.
9. Back up and verify the existing SQLite database before schema or storage migration. Do not silently discard existing office history.
10. Do not expose Vindora operational data to other tenants or public pages.

## Migration strategy — incremental, reversible

### Phase 0 — baseline (this document)
Record current structure and product boundaries. No runtime code or data changes.

### Phase 1 — decouple Vindora defaults
Move brand/company prompt, employee directory, employee templates, integration enablement, and workspace settings into explicit configuration/data. Preserve Vindora's current behavior through a dedicated Vindora workspace configuration. Remove no data and do not rename the current login route until compatibility is tested.

### Phase 2 — identity and workspace foundation
Introduce users, workspaces, memberships, roles, invitations, and session claims. Add workspace context to APIs and background tasks. Keep a controlled single-workspace compatibility adapter for the existing owner login during transition.

### Phase 3 — tenant-safe persistence
Add nullable/backfilled workspace ownership columns with explicit migration scripts; backfill all existing Vindora records to one dedicated workspace; verify row counts and relationships; then enforce non-null constraints after validation. Add automated cross-tenant denial tests. Evaluate PostgreSQL before commercial multi-tenant launch; SQLite may remain for local development only.

### Phase 4 — Super Admin shell and Command Center
Create separate route, layout, API permission dependency, navigation, overview metrics, customer/workspace list, operational health, and audit log. Do not grant platform-admin powers to the existing office login.

### Phase 5 — public site and Website Studio
Create CMS data model (pages, sections, assets, SEO, revisions, publication state), public renderer, preview tokens, publish/rollback actions, and media validation. Site content is editable from the admin console; code-level templates remain controlled by developers.

### Phase 6 — plans, billing, and commercial operations
Add plan entitlements, subscription state, metering, invoices/payment provider integration, webhook signature verification, grace periods, and suspension rules. Test idempotency and reconciliation before collecting real payments.

### Phase 7 — product hardening and launch
Security review, tenant-isolation suite, backup/restore drill, rate limits, observability, privacy/terms pages, support workflows, load tests, and pilot launch.

## First implementation slice after this baseline

Build a read-only Super Admin shell and navigation behind a new platform-admin authorization boundary, plus a platform overview API that returns only safe operational metadata. Do not implement customer mutation, billing, CMS publishing, or tenant migration in the same slice. This creates a real, reviewable first screen without risking the existing workspace.

## Acceptance gates

- Existing Vindora office login and core task/chat behavior continue working.
- The platform Super Admin cannot be reached with a workspace token.
- A workspace user cannot read another workspace's records, even by changing IDs.
- No public frontend contains secrets.
- Every CMS publish and privileged admin mutation is auditable and reversible where applicable.
- No code or data under `test/` is touched.
- Each phase is delivered in a separate branch/PR with validation and a rollback plan.
