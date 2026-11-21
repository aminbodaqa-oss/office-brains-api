# Platform Super Admin setup

The platform console is a separate entry point at `office/frontend/platform-admin.html`. It is not the customer office login.

## Required Bot Hosting environment variables

Set all three variables in the API deployment environment before attempting login:

- `PLATFORM_ADMIN_USERNAME`: dedicated platform-owner username. Do not reuse a customer/workspace credential.
- `PLATFORM_ADMIN_PASSWORD_HASH`: PBKDF2 password hash generated with the existing backend password utility.
- `PLATFORM_ADMIN_AUTH_SECRET`: a new random secret with at least 32 characters. It must be different from `OFFICE_AUTH_SECRET`.

Generate a password hash from the backend directory using a secure terminal session:

```bash
python -c "from auth import hash_password; print(hash_password(input('New platform admin password: ')))"
```

Copy the printed hash into `PLATFORM_ADMIN_PASSWORD_HASH`. Do not put the plain password or secret in GitHub, source files, frontend code, screenshots, or chat messages.

Generate a distinct signing secret with a password manager or a cryptographically secure generator, for example:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## First release behavior

- Login: `POST /api/platform/admin/login`.
- Overview: `GET /api/platform/admin/overview` with the returned Bearer token.
- Platform tokens have a dedicated audience and a 15-minute lifetime. They are not accepted by the existing workspace `require_owner` dependency.
- The overview is read-only and aggregate-only. It does not return customer records, task details, conversations, memories, or Vindora operational data.
- No refresh token is issued in this first slice; sign out and log in again after expiry.
- If the three environment variables are not configured, the API deliberately returns HTTP 503 and does not fall back to the existing office owner credentials.

## Deployment

The static console is served as `office/frontend/platform-admin.html` by the same frontend hosting process used for the existing office frontend. The API endpoints are served by the existing FastAPI deployment. After merging, configure the three environment variables in Bot Hosting and restart the API once. Do not change or remove the existing `OWNER_USERNAME`, `OWNER_PASSWORD_HASH`, or `OFFICE_AUTH_SECRET` settings.
