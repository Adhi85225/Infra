# Authentication

Users sign in with their **email address** and a password. There is no public
self-registration.

## Sign-in

```
POST /api/v1/auth/login   { "email": "...", "password": "..." }
```

Server-side sequence:

1. Look the user up by lower-cased email.
2. **No such user** → hash the supplied password anyway (so the response time
   does not distinguish the case), record a failed-login audit entry, and return
   the *same* `invalid_credentials` error a wrong password produces.
3. **Locked** → return `account_locked`.
4. **Wrong password** → increment the failure counter, lock the account once it
   reaches `MAX_FAILED_LOGINS`, return `invalid_credentials`.
5. **Not ACTIVE** → return `account_inactive`. Checked *after* the password, so
   an attacker without the password learns nothing.
6. Success → reset counters, record `last_login_at`, transparently re-hash if
   the Argon2 parameters have since changed, create a session.

Response:

```json
{
  "access_token": "eyJ…",
  "token_type": "Bearer",
  "expires_at": "2026-09-04T15:00:00Z",
  "must_change_password": false,
  "user": { "...": "..." },
  "permissions": [ { "module_key": "DASHBOARD", "access_level": "COMPLETE", "...": "..." } ]
}
```

Two cookies are set at the same time:

| Cookie | Flags | Purpose |
| ------ | ----- | ------- |
| `ght_refresh` | HttpOnly, SameSite, Secure in production, path `/api/v1/auth` | the refresh credential |
| `ght_csrf` | readable by JS | echoed in `X-CSRF-Token` on cookie-authenticated calls |

The refresh token is **never** in the response body. The cookie is scoped to the
auth path so it is not attached to ordinary API traffic.

## Sessions

| Token | TTL | Location |
| ----- | --- | -------- |
| Access | `ACCESS_TOKEN_TTL_MINUTES` (15) | browser memory |
| Refresh | `REFRESH_TOKEN_TTL_DAYS` (7) | httpOnly cookie; SHA-256 digest in `sessions` |

### Every request is re-validated

Possession of a valid JWT is not sufficient. `get_current_user` also:

- checks the token's `jti` against the Redis deny-list,
- reloads the user and rejects any non-ACTIVE status,
- reloads the backing session row and rejects it if revoked.

So deactivating a user or revoking a session takes effect on their **next
request**, not at token expiry.

### Rotation and theft detection

```
POST /api/v1/auth/refresh      (cookie + X-CSRF-Token)
```

Each refresh revokes the presented token (`revoked_reason = "rotated"`) and
issues a successor with `rotated_from_id` pointing at it. The successor inherits
the original expiry — rotation does not extend a session indefinitely.

If a **revoked** refresh token is presented, two parties hold that token. The
whole session family is revoked (walking `rotated_from_id` in both directions),
a `TOKEN_REUSE_DETECTED` audit entry is written, and the caller must sign in
again.

Because a rotated session row is revoked, an access token minted before the
rotation stops working immediately. That is intentional: the alternative left
pre-logout tokens alive for their full remaining lifetime.

### CSRF

`/auth/refresh` and `/auth/logout` are the only cookie-authenticated endpoints,
so they are the only CSRF-reachable surface. Both require `X-CSRF-Token` to
match the readable `ght_csrf` cookie — a cross-site request carries the cookies
but cannot read the value to set the header.

Every other endpoint authenticates with a `Bearer` header, which a cross-site
form cannot set.

### Sign-out

```
POST /api/v1/auth/logout       (cookie + X-CSRF-Token)
```

Revokes the session family, deny-lists the access token's `jti` for its
remaining lifetime, and clears both cookies. Authentication is *optional* here:
signing out must succeed even with an expired token so the client can always
clear its state.

## First-login password change

Admin-created accounts are flagged `must_change_password`. While it is set, a
dedicated dependency (`get_active_user`) rejects **every** protected endpoint
with `403 password_change_required`. Only three routes use plain
`get_current_user` and stay reachable: `/auth/me`, `/auth/change-password` and
`/auth/logout`.

The enforcement is server-side. The UI redirect to `/change-password` mirrors it
but is not what enforces it.

On success the flag clears and the endpoint returns a **new session**, so the
user continues without being bounced to the sign-in screen.

## Changing a password

```
POST /api/v1/auth/change-password
{ "current_password": "...", "new_password": "...", "confirm_password": "..." }
```

Checks, in order: current password correct → confirmation matches → policy
satisfied → not the current password → not in the last
`PASSWORD_HISTORY_DEPTH` passwords.

Then: the old hash moves to history, **all** sessions are revoked, and a fresh
session is issued to the caller. Anyone holding the old credential is signed out.

## Forgot / reset password

```
POST /api/v1/auth/forgot-password   { "email": "..." }   -> always 202
POST /api/v1/auth/reset-password    { "token": "...", "new_password": "...", "confirm_password": "..." }
```

1. `/forgot-password` returns an identical 202 whether or not the address
   exists, and whether or not the account is active. It cannot be used to
   enumerate accounts.
2. For an active account: any outstanding tokens are invalidated (only the
   newest link works), a 64-character URL-safe token is generated, and **only
   its SHA-256 digest** is stored with an expiry of
   `PASSWORD_RESET_TTL_MINUTES`.
3. The email is dispatched through the transport. In Phase 1 that means the
   developer outbox — see [SMTP.md](SMTP.md).
4. `/reset-password` accepts the token only while unused and unexpired, applies
   the same password policy, marks it used, and **revokes every session** for
   that user.

Both endpoints are rate limited.

## Password policy

Configurable; enforced server-side and published at
`GET /api/v1/auth/password-policy` so the UI renders the rules without
duplicating them.

Defaults: minimum 12 characters, upper + lower + digit + symbol, not a common
password, not containing the local part of the email, not one of the last 3.

## Hashing

**Argon2id** via `argon2-cffi`, defaults `time_cost=3`, `memory_cost=64 MiB`,
`parallelism=1`.

Cost comes from configuration so tests can run cheaply, and production refuses
to start below the OWASP floor (19 MiB / 2 iterations). `check_needs_rehash`
means changing the parameters upgrades each user's hash on their next sign-in,
with no migration.

## Account lockout

After `MAX_FAILED_LOGINS` (5) consecutive failures an account locks for
`LOCKOUT_MINUTES` (15). A successful sign-in, an admin password reset, or a
completed reset clears it.

Lockout is checked *before* password verification, so a locked account does not
consume Argon2 work. This does reveal that an address exists — an accepted
trade-off, discussed in [SECURITY.md](SECURITY.md#accepted-limitations).

## Audit trail

Recorded: `LOGIN_SUCCESS`, `LOGIN_FAILED` (with reason), `LOGOUT`,
`TOKEN_REFRESHED`, `TOKEN_REUSE_DETECTED`, `ACCOUNT_LOCKED`,
`PASSWORD_CHANGED`, `PASSWORD_RESET_REQUESTED`, `PASSWORD_RESET_COMPLETED`,
`ADMIN_PASSWORD_RESET`.

Context is redacted before it is persisted — a password or token cannot reach
the audit table even if a caller passes one.
