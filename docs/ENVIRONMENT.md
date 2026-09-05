# Environment Variables

Every setting comes from the environment. [`.env.example`](../.env.example) is
the canonical template with placeholder values only.

```bash
cp .env.example .env      # .env is git-ignored — never commit it
```

Generate secrets with `openssl rand -base64 48`.

## Application

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `APP_NAME` | `Global Infrastructure` | Also the JWT issuer |
| `ENVIRONMENT` | `development` | `development` \| `test` \| `production` |
| `DEBUG` | `false` | Verbose logging. Refused in production |
| `FRONTEND_BASE_URL` | `http://localhost:8080` | **Used to build password-reset links.** Wrong value = dead links |

## Ports (published on the Docker host)

| Variable | Default |
| -------- | ------- |
| `API_PORT` | `8000` |
| `WEB_PORT` | `8080` |
| `POSTGRES_PORT` | `5434` |
| `REDIS_PORT` | `6380` |

Non-standard database/Redis ports avoid clashing with other local stacks.

## Database

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `POSTGRES_USER` | `ght` | |
| `POSTGRES_PASSWORD` | — | **Required.** Compose refuses to start without it |
| `POSTGRES_DB` | `ght` | |
| `DATABASE_URL` | — | `postgresql+asyncpg://user:pass@host:5432/db`. Compose overrides the host to `db` |
| `DATABASE_ECHO` | `false` | Log SQL. Development only |
| `DATABASE_POOL_SIZE` | `10` | |
| `DATABASE_MAX_OVERFLOW` | `10` | |

## Redis

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `REDIS_ENABLED` | `true` | `false` uses in-process fallbacks |
| `REDIS_URL` | `redis://redis:6379/0` | |

Used for rate limits, the permission cache and the access-token deny-list. If
Redis is unreachable the application still serves requests — see
[SECURITY.md](SECURITY.md#accepted-limitations).

## Security

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `JWT_SECRET` | dev placeholder | **Must be ≥32 random characters in production; startup fails otherwise** |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_TTL_MINUTES` | `15` | Keep short — this is the revocation window |
| `REFRESH_TOKEN_TTL_DAYS` | `7` | How long "stay signed in" lasts |
| `PASSWORD_RESET_TTL_MINUTES` | `30` | Reset link lifetime |
| `COOKIE_SECURE` | `false` | **Must be `true` in production** (requires HTTPS) |
| `COOKIE_SAMESITE` | `lax` | `lax` \| `strict` \| `none` |
| `COOKIE_DOMAIN` | unset | Set when web and API share a parent domain |

## Password policy

| Variable | Default |
| -------- | ------- |
| `PASSWORD_MIN_LENGTH` | `12` |
| `PASSWORD_MAX_LENGTH` | `128` |
| `PASSWORD_REQUIRE_UPPER` | `true` |
| `PASSWORD_REQUIRE_LOWER` | `true` |
| `PASSWORD_REQUIRE_DIGIT` | `true` |
| `PASSWORD_REQUIRE_SYMBOL` | `true` |
| `PASSWORD_HISTORY_DEPTH` | `3` |

## Password hashing (Argon2id)

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `PASSWORD_HASH_TIME_COST` | `3` | Production floor: 2 |
| `PASSWORD_HASH_MEMORY_COST_KIB` | `65536` (64 MiB) | Production floor: 19456 |
| `PASSWORD_HASH_PARALLELISM` | `1` | |

Raising these upgrades each user's hash automatically at their next sign-in.
Memory cost is per concurrent hash — size it against your worker count.

## Lockout & rate limits

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `MAX_FAILED_LOGINS` | `5` | |
| `LOCKOUT_MINUTES` | `15` | |
| `RATE_LIMIT_LOGIN` | `10/60` | `requests/seconds`, per client |
| `RATE_LIMIT_FORGOT_PASSWORD` | `5/900` | |
| `RATE_LIMIT_RESET_PASSWORD` | `10/900` | |
| `RATE_LIMIT_DEFAULT` | `300/60` | |

## CORS

| Variable | Default |
| -------- | ------- |
| `CORS_ORIGINS` | `http://localhost:8080,http://localhost:5174` |

Comma-separated exact origins. Credentials are allowed, so `*` is not valid —
list every origin that serves the frontend.

## Email

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `EMAIL_TRANSPORT` | `log` | `log` \| `smtp`. See [SMTP.md](SMTP.md) |
| `SMTP_HOST` | empty | |
| `SMTP_PORT` | `587` | |
| `SMTP_USERNAME` | empty | |
| `SMTP_PASSWORD` | empty | **Secret** |
| `SMTP_SECURE` | `starttls` | `none` \| `starttls` \| `ssl` |
| `SMTP_FROM_EMAIL` | `no-reply@example.internal` | |
| `SMTP_FROM_NAME` | `Global Infrastructure` | |
| `DEV_OUTBOX_DIR` | `var/dev-outbox` | Never written to in production |

## Bootstrap administrator

Used by the seed, and only when the database contains no users.

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `BOOTSTRAP_ADMIN_EMAIL` | `superadmin@example.internal` | |
| `BOOTSTRAP_ADMIN_PASSWORD` | empty | Leave empty to have one generated and printed **once** |
| `BOOTSTRAP_ADMIN_FIRST_NAME` | `Super` | |
| `BOOTSTRAP_ADMIN_LAST_NAME` | `Admin` | |

The bootstrap account always requires a password change at first sign-in.

## Frontend (build time)

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | **Baked into the bundle at build time.** Changing it requires rebuilding `web` |

## Production checklist

Startup **fails** if any of these are wrong:

- [ ] `ENVIRONMENT=production`
- [ ] `JWT_SECRET` — random, ≥32 characters, not the default
- [ ] `COOKIE_SECURE=true`
- [ ] `DEBUG=false`
- [ ] `PASSWORD_HASH_MEMORY_COST_KIB` ≥ 19456 and `PASSWORD_HASH_TIME_COST` ≥ 2

Also verify (not enforced automatically):

- [ ] `POSTGRES_PASSWORD` is strong and unique
- [ ] `FRONTEND_BASE_URL` is the real public URL
- [ ] `CORS_ORIGINS` lists only real origins
- [ ] `VITE_API_BASE_URL` matches the deployed API and the image was rebuilt
- [ ] The database port mapping is removed from `docker-compose.yml`
- [ ] `.env` is not committed
