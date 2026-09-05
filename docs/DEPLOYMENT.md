# Deployment

## Stack

Four services defined in `docker-compose.yml`:

| Service | Image | Host port | Purpose |
| ------- | ----- | --------- | ------- |
| `db` | `postgres:16-alpine` | `5434` | System of record |
| `redis` | `redis:7-alpine` | `6380` | Rate limits, permission cache, token deny-list |
| `api` | built from `backend/` | `8000` | FastAPI |
| `web` | built from `frontend/` | `8080` | nginx serving the SPA |

`db` and `redis` are on a `backend` network the `web` container cannot reach.

## Deploy

```bash
cp .env.example .env
# edit .env — at minimum: POSTGRES_PASSWORD, JWT_SECRET
docker compose -f docker-compose.yml up -d --build
```

`-f docker-compose.yml` bypasses `docker-compose.override.yml`, which exists to
keep local development running only `db` and `redis`.

On start the API container:

1. waits for PostgreSQL (up to 90 s),
2. runs `alembic upgrade head`,
3. runs `python -m app.db.seed`,
4. starts uvicorn.

All three steps are idempotent, so restarting is always safe.

### First sign-in

If the database had no users, the seed creates a Super Admin and prints the
generated password **once**:

```bash
docker compose logs api | grep -A4 "BOOTSTRAP SUPER ADMIN"
```

Sign in at `http://localhost:8080/login`. A password change is enforced
immediately.

Alternatively set `BOOTSTRAP_ADMIN_PASSWORD` in `.env` before the first start.

### Verify

```bash
docker compose ps                                  # all four healthy
curl -s http://localhost:8000/health/ready | jq    # database + redis ok
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/
```

## Operations

```bash
docker compose logs -f api                 # follow API logs
docker compose logs -f                     # everything
docker compose restart api                 # restart one service
docker compose up -d --build api           # rebuild and redeploy
docker compose down                        # stop (data kept)
docker compose down -v                     # stop and DESTROY the database
```

### Database

```bash
# Shell
docker compose exec db psql -U ght -d ght

# Backup
docker compose exec -T db pg_dump -U ght -d ght | gzip > backup-$(date +%F).sql.gz

# Restore (into an empty database)
gunzip -c backup-2026-09-04.sql.gz | docker compose exec -T db psql -U ght -d ght

# Migration status
docker compose exec api alembic current
docker compose exec api alembic history
```

### Manual seed / migrate

```bash
docker compose exec api alembic upgrade head
docker compose exec api python -m app.db.seed
```

### Retrieve a password reset link (before SMTP is configured)

```bash
docker compose exec api sh -c 'cat "$(ls -t /app/var/dev-outbox/*.txt | head -1)"'
```

See [SMTP.md](SMTP.md).

## Upgrading

```bash
git pull
docker compose -f docker-compose.yml up -d --build
```

Migrations run automatically. Take a backup first for anything non-trivial.

## Production checklist

**Before the first production start**

- [ ] `ENVIRONMENT=production`
- [ ] `JWT_SECRET` — `openssl rand -base64 48`
- [ ] `POSTGRES_PASSWORD` — strong and unique
- [ ] `COOKIE_SECURE=true` (requires HTTPS)
- [ ] `DEBUG=false`
- [ ] `FRONTEND_BASE_URL` — the real public URL (reset links depend on it)
- [ ] `CORS_ORIGINS` — real origins only
- [ ] `VITE_API_BASE_URL` — the real API URL, then **rebuild** `web`
- [ ] Remove the `ports:` mapping from `db` (and `redis`) in
      `docker-compose.yml`
- [ ] `.env` is not committed and has restrictive file permissions

The application refuses to start if `JWT_SECRET`, `COOKIE_SECURE`, `DEBUG` or
the hash cost are unsafe for production. The rest of the list is on you.

**Reverse proxy**

Terminate TLS in front of the stack. The proxy **must overwrite**
`X-Forwarded-For` rather than appending to it — the API trusts the first value
for rate limiting and audit records.

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;   # overwrite, not append
    proxy_set_header X-Forwarded-Proto $scheme;
}
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**Ongoing**

- [ ] Automate PostgreSQL backups and *test a restore*
- [ ] Ship logs somewhere durable
- [ ] Alert on `TOKEN_REUSE_DETECTED`, `ACCOUNT_LOCKED`, `LOGIN_FAILED` bursts

## Scaling

- `UVICORN_WORKERS` (default 2) sets API worker processes.
- The API is stateless — run several replicas behind a load balancer.
- **Redis becomes mandatory** with more than one replica, or rate limits and the
  token deny-list will be per-process.
- PostgreSQL is the only stateful service.

## Troubleshooting

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| `api` restarts repeatedly | Insecure production config, or the database is unreachable | `docker compose logs api` — the startup validator names the problem |
| `POSTGRES_PASSWORD must be set` | Missing `.env` | `cp .env.example .env` and edit |
| Login returns a CORS error | Origin not listed | Add it to `CORS_ORIGINS`, restart `api` |
| Frontend calls the wrong API | `VITE_API_BASE_URL` is baked in at build time | Fix it and `docker compose up -d --build web` |
| Sign-in works, next request is 401 | `COOKIE_SECURE=true` without HTTPS, so the refresh cookie is dropped | Use HTTPS, or set `false` for local testing |
| Reset links point at the wrong host | `FRONTEND_BASE_URL` | Fix and restart `api` |
| Port already in use | Another local stack | Change `*_PORT` in `.env` |
| `web` restarts | nginx cannot write its pid file | Should not occur; check the image was rebuilt after the fix |
