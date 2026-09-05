# Security

Security is treated as a functional requirement here, not a hardening pass. This
document states what is implemented, what is deliberately not, and why.

## Controls

### Passwords

| Control | Implementation |
| ------- | -------------- |
| Hashing | Argon2id (`argon2-cffi`), 64 MiB / t=3 / p=1 by default |
| Configurable cost | From settings, with production floors (19 MiB, t≥2) checked at startup |
| Automatic upgrade | `check_needs_rehash` re-hashes on sign-in when parameters change |
| Policy | Length, character classes, common-password list, must not contain the email local part |
| History | Last `PASSWORD_HISTORY_DEPTH` hashes retained; reuse refused |
| Never stored in plaintext | Only hashes are persisted |
| Never logged | Process-wide redaction filter |

Temporary passwords are generated with `secrets`, always satisfy the policy, are
returned exactly once, and always carry a forced change.

### Tokens

| Token | Storage | Lifetime | Notes |
| ----- | ------- | -------- | ----- |
| Access (JWT) | Browser memory | 15 min | Signed HS256; `sub`, `sid`, `jti` required |
| Refresh | httpOnly cookie; **SHA-256 digest** in the database | 7 days | Rotates on every use |
| Reset | Emailed once; **SHA-256 digest** stored | 30 min | Single use |
| CSRF | Readable cookie | 7 days | Double-submit |

A database disclosure yields no usable refresh or reset token — only digests are
stored. SHA-256 is the right choice here (fast, indexable) because these are
high-entropy random values, not user-chosen secrets.

### Sessions

- Refresh rotation with `rotated_from_id` chaining.
- **Reuse detection**: replaying a revoked token revokes the whole family and
  writes a `TOKEN_REUSE_DETECTED` audit entry.
- Rotation does not extend the original expiry.
- User status and session validity are re-read from the database on **every
  request** — deactivation and revocation take effect immediately.
- Password change or reset revokes all sessions.

### Authentication attacks

| Attack | Mitigation |
| ------ | ---------- |
| Credential stuffing | Per-account lockout (5 failures / 15 min) + per-client rate limiting |
| Account enumeration via sign-in | Identical response and comparable timing for unknown email and wrong password; status checked only after the password verifies |
| Account enumeration via forgot-password | Always the same 202 |
| Brute-forcing reset tokens | 64-char URL-safe tokens (≈384 bits), short expiry, rate limited |
| Session fixation | A new session is created on every sign-in and password change |
| Token theft | Short access TTL, rotation, family revocation on reuse |
| Privilege escalation | Explicit guards — see [AUTHORIZATION.md](AUTHORIZATION.md#escalation-guards) |

### Transport & browser

- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, a restrictive `Content-Security-Policy`, and
  `Cache-Control: no-store` on API responses.
- HSTS when `COOKIE_SECURE=true`.
- Cookies: `HttpOnly` on the refresh token, `SameSite`, `Secure` in production,
  and a path scope limiting the refresh cookie to the auth routes.
- CORS restricted to an explicit origin list; credentials allowed, so `*` is not
  permitted.
- Interactive API docs and the OpenAPI schema are disabled in production.

### Input handling

- Every request body and query parameter is validated by Pydantic.
- All database access goes through SQLAlchemy with bound parameters — no string
  interpolation of SQL anywhere.
- React escapes rendered content by default; the application uses no
  `dangerouslySetInnerHTML`.
- Response schemas are explicit allow-lists — `password_hash` cannot be
  serialised by accident.

### Secrets

- Sourced exclusively from the environment.
- `.env` is git-ignored; `.env.example` contains placeholders only.
- No secret appears in `docker-compose.yml`.
- Production refuses to start with the default `JWT_SECRET`, insecure cookies,
  debug mode, or a weak hash cost.

### Logging

A `RedactionFilter` is installed on the root logger, so it applies to every
logger including third-party libraries. It masks `password`, `token`,
`authorization`, `cookie`, `secret`, `api_key` and related keys, recursively
through nested structures, and also catches inline `password=…` patterns in
free-form strings. Audit context is redacted before it is persisted.

### Containers

- Both images run as non-root (`app`, `nginx`).
- Multi-stage builds — no compiler toolchain in the runtime image.
- `db` and `redis` are on a network the web container cannot reach.
- Health checks on all four services; `tini` reaps zombie processes.

## Accepted limitations

Each is a deliberate decision, not an oversight.

| Limitation | Why | Mitigation |
| ---------- | --- | ---------- |
| **Email is not delivered** | Explicitly out of Phase 1 scope | Temporary passwords and reset links are handed over manually; the seam is one method away from working ([SMTP.md](SMTP.md)) |
| **Access-token deny-list needs Redis** | Redis is optional by design | Sessions are still checked against the database every request, so revocation works regardless; without Redis a revoked *token* stays valid for ≤15 min only if its session row is somehow still live |
| **Locked accounts are identifiable** | Lockout must be checked before hashing to be worth anything | Rate limiting bounds probing; reaching lockout already requires 5 attempts against a real account |
| **Rate limits are per-process without Redis** | Graceful degradation was chosen over hard failure | Run Redis in any multi-node deployment |
| **No per-user permission overrides** | Not required by Phase 1 | The resolver is structured to accept an additional grant source |
| **No 2FA** | Out of Phase 1 scope | Session model already supports adding a step |
| **`X-Forwarded-For` is trusted** | The app is expected to sit behind the bundled proxy | The proxy must *overwrite*, not append to, the header |
| **Dev outbox writes tokens to disk** | Needed because logs redact tokens | Disabled entirely in production; `backend/var/` is git-ignored |
| **`USER` role permissions are placeholders** | The requirements defer them | Documented; adjustable at runtime with no deployment |

## Deployment hardening

Beyond the automatic checks:

1. **Terminate TLS in front of the stack** and set `COOKIE_SECURE=true`.
2. **Remove the database port mapping** from `docker-compose.yml`.
3. **Rotate `JWT_SECRET`** on suspicion of compromise — this invalidates all
   access tokens; refresh sessions survive, so revoke them too if needed.
4. **Back up PostgreSQL** — it is the only stateful service. Redis holds nothing
   that cannot be rebuilt.
5. **Ship the logs** somewhere durable; they are the audit trail's companion.
6. **Watch for** `TOKEN_REUSE_DETECTED`, bursts of `LOGIN_FAILED`, and
   `ACCOUNT_LOCKED` — these are the signals worth alerting on.

## Reporting

Report suspected vulnerabilities to the platform owners privately. Do not open a
public issue.
