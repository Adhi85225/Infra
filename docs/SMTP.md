# SMTP / Email Configuration

> **Phase 1 does not deliver real email.** The configuration surface, the
> transport seam and the message templates all exist and are exercised, but
> `SMTPTransport.send` is deliberately unimplemented. This document is the
> checklist for turning delivery on.

## What happens today

`EMAIL_TRANSPORT=log` (the default):

1. The message is rendered from its template.
2. A **redacted** summary is written to the application log — recipient,
   subject, sender, tags. No token, ever.
3. The **full body**, including the reset link, is written to a file in the
   developer outbox: `backend/var/dev-outbox/`.

The split exists because the logger redacts tokens process-wide by design. That
is correct for production and would make the log transport useless in
development, so the readable copy goes to a file instead — and
`write_to_outbox()` returns immediately without writing when
`ENVIRONMENT=production`.

### Getting a password reset link in development

```bash
# Local
ls -t backend/var/dev-outbox/ | head -1
cat backend/var/dev-outbox/$(ls -t backend/var/dev-outbox | head -1)

# Docker
docker compose exec api sh -c 'cat "$(ls -t /app/var/dev-outbox/*.txt | head -1)"'
```

The file contains the full URL, e.g.
`http://localhost:8080/reset-password?token=…`.

### Getting a new user's temporary password

It is returned **once** in the `POST /api/v1/users` response and shown in the
"User created" dialog. It is never logged and never stored in plaintext. Until
SMTP works, hand it over through a secure channel.

## Configuration

All values come from the environment. **Never commit credentials.**

| Variable | Example | Meaning |
| -------- | ------- | ------- |
| `EMAIL_TRANSPORT` | `log` \| `smtp` | `log` = outbox; `smtp` = real delivery |
| `SMTP_HOST` | `smtp.example.com` | server hostname |
| `SMTP_PORT` | `587` | `587` STARTTLS · `465` SSL · `25` unencrypted |
| `SMTP_USERNAME` | `no-reply@example.com` | auth user |
| `SMTP_PASSWORD` | *(secret)* | auth password |
| `SMTP_SECURE` | `starttls` \| `ssl` \| `none` | connection security |
| `SMTP_FROM_EMAIL` | `no-reply@example.com` | envelope/header sender |
| `SMTP_FROM_NAME` | `Global Infrastructure` | display name |
| `FRONTEND_BASE_URL` | `https://tools.example.com` | **used to build reset links — must be the URL users actually reach** |

`FRONTEND_BASE_URL` is the one that breaks silently: if it is wrong, emails send
successfully and every reset link is dead.

### Where to put them

- **Docker Compose** — in `.env` at the repository root. `docker-compose.yml`
  passes it via `env_file`, so no secret is ever written into the compose file.
- **Local development** — in `.env`; `backend/.env` is a symlink to it.
- **Production** — inject via your orchestrator's secret mechanism.

## Enabling real delivery

### 1. Add a dependency

```bash
echo "aiosmtplib~=3.0.0" >> backend/requirements.txt
```

### 2. Implement one method

The **only** code change is `SMTPTransport.send` in
`backend/app/services/email/transports.py`:

```python
class SMTPTransport(EmailTransport):
    name = "smtp"

    async def send(self, message: EmailMessage) -> None:
        import aiosmtplib
        from email.message import EmailMessage as MIMEMessage

        mime = MIMEMessage()
        mime["From"] = f"{settings.smtp.from_name} <{settings.smtp.from_email}>"
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text_body)
        if message.html_body:
            mime.add_alternative(message.html_body, subtype="html")

        await aiosmtplib.send(
            mime,
            hostname=settings.smtp.host,
            port=settings.smtp.port,
            username=settings.smtp.username or None,
            password=settings.smtp.password or None,
            start_tls=settings.smtp.secure == "starttls",
            use_tls=settings.smtp.secure == "ssl",
            timeout=15,
        )
```

Nothing else changes. `EmailService.send` already catches and logs failures so a
mail outage cannot break a request or leak whether an address exists.

### 3. Configure and restart

```bash
# .env
EMAIL_TRANSPORT=smtp
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=no-reply@example.com
SMTP_PASSWORD=…
SMTP_SECURE=starttls
SMTP_FROM_EMAIL=no-reply@example.com
SMTP_FROM_NAME=Global Infrastructure
FRONTEND_BASE_URL=https://tools.example.com
```

```bash
docker compose up -d --build api
```

If `EMAIL_TRANSPORT=smtp` but `SMTP_HOST` is empty, the application logs a
warning and falls back to the log transport rather than failing requests.

### 4. Verify

```bash
curl -X POST http://localhost:8000/api/v1/auth/forgot-password \
  -H 'Content-Type: application/json' \
  -d '{"email":"a-real-user@example.com"}'

docker compose logs api | grep -E 'email\.(dispatched|failed|not_sent)'
```

`email.failed` means delivery was attempted and rejected — the log line carries
the reason.

## Relevant URLs

The routes that email touches. Full list in [ROUTES.md](ROUTES.md).

| Page | URL | Purpose |
| ---- | --- | ------- |
| Login | `{FRONTEND_BASE_URL}/login` | linked from the welcome email |
| Forgot password | `{FRONTEND_BASE_URL}/forgot-password` | where a reset is requested |
| **Reset password** | `{FRONTEND_BASE_URL}/reset-password?token=…` | **the link in the reset email** |
| Change password | `{FRONTEND_BASE_URL}/change-password` | forced first-login change |

| API endpoint | Method | Purpose |
| ------------ | ------ | ------- |
| `/api/v1/auth/forgot-password` | POST | triggers the reset email |
| `/api/v1/auth/reset-password` | POST | consumes the token |
| `/api/v1/auth/change-password` | POST | authenticated change |
| `/api/v1/users` | POST | triggers the welcome email |

## Messages sent

| Template | Trigger | Contains |
| -------- | ------- | -------- |
| `build_password_reset_email` | `/auth/forgot-password` for an active account | reset URL, expiry |
| `build_welcome_email` | user created, or admin password reset | login URL, email, temporary password |

Both are plain text: these are transactional security emails, and plain text
avoids rendering inconsistencies across mail clients.

## Security notes

- Never commit real credentials. `.env` is git-ignored.
- Use a dedicated no-reply mailbox with a scoped credential, not a personal one.
- Prefer `starttls` on 587, or `ssl` on 465. Avoid `none` outside a trusted
  network.
- Reset links carry a single-use, time-limited token. Keep
  `PASSWORD_RESET_TTL_MINUTES` short (default 30).
- The dev outbox writes tokens to disk. It is disabled in production, and
  `backend/var/` is git-ignored — but clean it up in shared environments.
