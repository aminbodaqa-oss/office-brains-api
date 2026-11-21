# Platform Super Admin setup

The platform console is a separate entry point at `office/frontend/platform-admin.html`. It uses the **same existing owner username and password** as the current office login. No second account or password hash is required.

## Required additional Bot Hosting setting

Set only this additional secret in the API deployment environment:

- `PLATFORM_ADMIN_AUTH_SECRET`: a new random secret with at least 32 characters, different from `OFFICE_AUTH_SECRET`.

Generate it securely with a password manager or a cryptographically secure generator, for example:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not put this secret in GitHub, source files, frontend code, screenshots, or chat messages.

## First release behavior

- Login: `POST /api/platform/admin/login`.
- It validates against the existing `OWNER_USERNAME` and the current password hash returned by the existing owner credential store (including a password changed through the office).
- Overview: `GET /api/platform/admin/overview` with the returned Bearer token.
- Platform tokens have a dedicated audience and a 15-minute lifetime. They are not accepted by the existing workspace `require_owner` dependency.
- The overview is read-only and aggregate-only. It does not return customer records, task details, conversations, memories, or Vindora operational data.
- No refresh token is issued in this first slice; sign out and log in again after expiry.
- Existing office login settings and password remain the source of truth.

## Deployment

After merging, add `PLATFORM_ADMIN_AUTH_SECRET` in Bot Hosting and restart the API once. Do not change or remove the existing `OWNER_USERNAME`, `OWNER_PASSWORD_HASH`, or `OFFICE_AUTH_SECRET` settings.
