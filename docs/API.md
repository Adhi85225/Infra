# API Reference

Base URL: `{API}/api/v1` — see [ROUTES.md](ROUTES.md).
Interactive schema at `{API}/docs` (non-production only).

## Conventions

**Authentication.** Send the access token as `Authorization: Bearer <token>`.
`/auth/refresh` and `/auth/logout` instead use the `ght_refresh` cookie and
require `X-CSRF-Token` matching the `ght_csrf` cookie.

**Errors.** Every failure uses one envelope:

```json
{ "error": { "code": "invalid_credentials", "message": "Invalid email or password.",
             "details": { "fields": { "email": "…" } } } }
```

Branch on `code`; `message` is safe to show a user.

| Status | Typical codes |
| ------ | ------------- |
| 401 | `unauthenticated`, `invalid_credentials`, `account_inactive`, `account_locked`, `token_expired`, `invalid_token`, `session_revoked` |
| 403 | `permission_denied`, `password_change_required`, `csrf_failed`, `self_role_change_denied` |
| 404 | `not_found` |
| 409 | `conflict`, `email_taken`, `role_key_taken`, `role_in_use` |
| 422 | `validation_error`, `invalid_reset_token`, `role_immutable`, `role_protected` |
| 429 | `rate_limited` (with `Retry-After`) |
| 500 | `internal_error` |

**Pagination.** List endpoints take `limit` and `offset` and return
`{ items, total, limit, offset }`, where `total` ignores pagination.

---

## Authentication

### `POST /auth/login`

```json
{ "email": "user@example.internal", "password": "…" }
```

`200` → `SessionResponse` (below). Sets `ght_refresh` and `ght_csrf` cookies.
`401` → `invalid_credentials` · `account_inactive` · `account_locked`.

**SessionResponse**

```json
{
  "access_token": "eyJ…",
  "token_type": "Bearer",
  "expires_at": "2026-09-04T15:00:00Z",
  "must_change_password": false,
  "user": { "id": "…", "email": "…", "full_name": "…", "status": "ACTIVE",
            "roles": [ { "key": "ADMIN", "name": "Admin", "…": "…" } ] },
  "permissions": [
    { "module_key": "DASHBOARD", "module_name": "Dashboard", "icon": "🏠",
      "route": "/dashboard", "access_level": "COMPLETE",
      "can_view": true, "can_manage": true, "is_implemented": true, "sort_order": 10 }
  ]
}
```

The refresh token is **not** in the body.

### `POST /auth/refresh`

Cookie + `X-CSRF-Token`. Rotates the refresh token and returns a new
`SessionResponse`. `401 session_revoked` if a rotated token is replayed — this
also revokes the entire session family.

### `POST /auth/logout`

Cookie + `X-CSRF-Token`. Bearer optional. Always `200`.

### `GET /auth/me`

Bearer. Returns `{ user, permissions, must_change_password }`. Reachable while a
password change is pending.

### `POST /auth/change-password`

```json
{ "current_password": "…", "new_password": "…", "confirm_password": "…" }
```

`200` → a **new** `SessionResponse`; all other sessions are revoked.
`422` → wrong current password, mismatch, policy violation, or password reuse.

### `POST /auth/forgot-password`

```json
{ "email": "user@example.internal" }
```

Always `202` with the same message, whether or not the account exists.

### `POST /auth/reset-password`

```json
{ "token": "…", "new_password": "…", "confirm_password": "…" }
```

`200` on success; revokes every session for the user.
`422 invalid_reset_token` if unknown, expired or already used.

### `GET /auth/password-policy`

Public. Returns the configured rules so a client need not duplicate them.

---

## Users

All require the `ACCESS_MANAGEMENT` module.

### `GET /users` — VIEW

Query: `search`, `status`, `role_key`, `limit` (1–100, default 25), `offset`.
Returns `Page<User>`. `password_hash` is never serialised.

### `GET /users/{user_id}` — VIEW

### `POST /users` — CREATE

```json
{ "email": "new@example.internal", "first_name": "New", "last_name": "Person",
  "role_keys": ["USER"], "status": "ACTIVE", "job_title": "Engineer" }
```

`201`:

```json
{ "user": { "…": "…" }, "temporary_password": "…", "email_delivered": true }
```

The temporary password is returned **once**. The account is flagged
`must_change_password`.

`409 email_taken` (case-insensitive) · `403` if a non-Super-Admin requests
`SUPER_ADMIN`.

### `PATCH /users/{user_id}` — UPDATE

Any of `first_name`, `last_name`, `status`, `job_title`, `department`, `phone`.
Setting a non-ACTIVE status revokes that user's sessions.
`422` if you change your own status · `403` if a non-Super-Admin targets a
Super Admin.

### `PUT /users/{user_id}/roles` — UPDATE

```json
{ "role_keys": ["ADMIN", "USER", "ASSET_MANAGER"] }
```

Replaces the set; any number of roles may be assigned, including custom ones.

`403 self_role_change_denied` when targeting your own account — nobody may
change their own roles.
`403` if granting `SUPER_ADMIN` without being one, or assigning a role that
grants more access than the caller holds.

### `POST /users/{user_id}/reset-password` — UPDATE

Issues a new temporary password, sets `must_change_password`, clears any
lockout, and revokes the user's sessions.

---

## Roles & Modules

All require the `ACCESS_MANAGEMENT` module.

### `GET /roles` — VIEW

Returns every role with `user_count` (how many users hold it) and `is_deletable`
(false for seeded system roles).

### `GET /roles/assignable-access-levels` — VIEW

`["NONE", "READ_ONLY", "COMPLETE"]`. Published so the UI never hard-codes the
list. The legacy `GUEST` level is not assignable — see
[AUTHORIZATION.md](AUTHORIZATION.md#the-deprecated-guest-level).

### `GET /roles/{role_id}` — VIEW

The role plus its full matrix: `{ "permissions": { "DASHBOARD": "COMPLETE", … } }`.

### `POST /roles` — CREATE

```json
{
  "name": "Asset Manager",
  "description": "Owns the hardware register.",
  "key": "ASSET_MANAGER",
  "permissions": { "ASSET_INVENTORY": "COMPLETE", "ZABBIX": "READ_ONLY" },
  "sort_order": 500
}
```

`key` is optional and derived from `name` when omitted (`"Asset Manager"` →
`ASSET_MANAGER`); it must match `^[A-Z][A-Z0-9_]{1,63}$`. Modules omitted from
`permissions` default to `NONE`.

`201` → the created role with its matrix.
`409 role_key_taken` · `422 validation_error` (bad key, unknown module, blank
name) · `403` if the caller would grant more access than they hold.

### `PATCH /roles/{role_id}` — UPDATE

`{ "name": "...", "description": "...", "sort_order": 500 }`. The `key` is
immutable. `403` if a non-Super-Admin targets `ADMIN`; `422 role_immutable` for
Super Admin.

### `PUT /roles/{role_id}/permissions` — UPDATE

```json
{ "permissions": { "ACCESS_MANAGEMENT": "READ_ONLY", "SETTINGS": "NONE" } }
```

Only the listed modules change. Takes effect immediately for every user holding
the role — the permission cache is invalidated, not merely expired.
`422 role_immutable` for Super Admin · `403` if a non-Super-Admin edits `ADMIN`,
or would grant more than they hold.

### `DELETE /roles/{role_id}` — UPDATE

`422 role_protected` for a seeded system role.
`409 role_in_use` when users still hold it — reassign them first.

### `GET /modules` — VIEW

The full module catalogue. Query `include_inactive` (default `false`).

---

## Audit

### `GET /audit-logs` — VIEW on `ACCESS_MANAGEMENT`

Query: `action`, `actor_user_id`, `entity_type`, `limit` (1–200, default 50),
`offset`. Returns `Page<AuditLogEntry>`, newest first. `context` is already
redacted.

---

## Health

`GET /health` → `{"status":"ok", …}`

`GET /health/ready` → `{"status":"ready","checks":{"database":"ok","redis":"ok"}}`.
Returns `503` only when the database is unreachable; Redis being down reports
`unavailable (degraded)` and stays ready.
