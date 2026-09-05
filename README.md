# Global Infrastructure

An internal, multipurpose **helper-tools platform**. It is built as a modular
system: authentication, authorization and the module catalogue form a shared
core, and each tool is added on top of it without touching that core.

> **Current state — Phase 1 complete.** Authentication, authorization, user and
> role administration (including **custom roles** with module-level
> permissions), a permission-aware dashboard, the audit foundation, Docker
> deployment and documentation are implemented and tested. The individual tools
> (Team Members, Asset Inventory, Zabbix, …) are deliberately **placeholders**.
> See [PROJECT_STATUS.md](PROJECT_STATUS.md).

---

## Stack

| Layer     | Technology                                              |
| --------- | ------------------------------------------------------- |
| Frontend  | React 18, TypeScript, Vite, Tailwind CSS, React Router 6 |
| Backend   | FastAPI, SQLAlchemy 2 (async), Pydantic v2, Alembic      |
| Database  | PostgreSQL 16                                            |
| Cache     | Redis 7 — rate limits, permission cache, token deny-list |
| Runtime   | Docker + Docker Compose                                  |

## Quick start

```bash
cp .env.example .env      # then edit: set JWT_SECRET and POSTGRES_PASSWORD
docker compose -f docker-compose.yml up -d --build
```

Migrations and seeding run automatically on API start. Read the generated
bootstrap administrator password out of the log **once**:

```bash
docker compose logs api | grep -A4 "BOOTSTRAP SUPER ADMIN"
```

| Service  | URL                            |
| -------- | ------------------------------ |
| Web app  | http://localhost:8080          |
| API      | http://localhost:8000          |
| API docs | http://localhost:8000/docs     |
| Health   | http://localhost:8000/health   |

Sign in at http://localhost:8080/login with that email and password; you will be
required to choose a new password immediately.

Full instructions, including local (non-Docker) development:
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) and
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Repository layout

```
.
├── backend/              FastAPI application
│   ├── app/
│   │   ├── api/          HTTP layer (routes + auth/authorization dependencies)
│   │   ├── core/         config, database, redis, security, logging, errors
│   │   ├── models/       SQLAlchemy models
│   │   ├── modules/      the module (tool) registry
│   │   ├── schemas/      Pydantic request/response contracts
│   │   ├── services/     business logic, incl. the permission service
│   │   └── db/seed.py    idempotent role/module/bootstrap seeding
│   ├── alembic/          database migrations
│   └── tests/            pytest suite (158 tests)
├── frontend/             React SPA
│   └── src/
│       ├── auth/         auth context + client-side permission helpers
│       ├── components/   layout and UI primitives
│       ├── pages/        screens
│       └── lib/          API client and shared types
├── docs/                 project documentation
├── docker-compose.yml    production-shaped stack
└── .env.example          every configuration variable, documented
```

## Documentation

| Document                                       | Contents                                        |
| ---------------------------------------------- | ----------------------------------------------- |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md)         | System design and the reasoning behind it       |
| [REQUIREMENTS.md](docs/REQUIREMENTS.md)         | Phase 1 requirements traced to implementation   |
| [DATABASE.md](docs/DATABASE.md)                 | Schema, relationships, migrations               |
| [AUTHENTICATION.md](docs/AUTHENTICATION.md)     | Sign-in, sessions, password flows               |
| [AUTHORIZATION.md](docs/AUTHORIZATION.md)       | Roles, module access levels, enforcement        |
| [API.md](docs/API.md)                           | Endpoint reference                              |
| [ROUTES.md](docs/ROUTES.md)                     | Every frontend route and API endpoint URL       |
| [SMTP.md](docs/SMTP.md)                         | **Where to add SMTP configuration later**       |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md)             | Docker deployment and operations                |
| [ENVIRONMENT.md](docs/ENVIRONMENT.md)           | Every environment variable                      |
| [SECURITY.md](docs/SECURITY.md)                 | Security model, controls, known limitations     |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md)           | Local setup, testing, adding a module           |
| [ROADMAP.md](docs/ROADMAP.md)                   | Phases beyond Phase 1                           |

Project tracking: [PRIORITY.md](PRIORITY.md) ·
[PROJECT_STATUS.md](PROJECT_STATUS.md) · [CHANGELOG.md](CHANGELOG.md)

## Testing

```bash
# Backend (229 tests)
cd backend
docker compose -f ../docker-compose.yml up -d db redis   # test dependencies
./.venv/bin/pytest

# Frontend (31 tests)
cd frontend
npm test
```

## Security notes

- No public self-registration — accounts are created by an administrator.
- Passwords are hashed with Argon2id; refresh and reset tokens are stored only
  as SHA-256 digests.
- Authorization is enforced **server-side** on every request. The dashboard
  shows only the tools a user may open, but hiding a card is a convenience —
  direct URLs and direct API calls are refused by the same central check.
- Nobody may change their own roles, or grant a role more access than they hold.
- No secrets are committed. `.env` is git-ignored; `.env.example` holds
  placeholders only.
