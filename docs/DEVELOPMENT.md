# Development

## Prerequisites

Docker + Docker Compose, Python 3.12+, Node.js 20+.

## Setup

```bash
cp .env.example .env
# For host-based development, point the app at the published container ports:
#   DATABASE_URL=postgresql+asyncpg://ght:change-me-in-production@localhost:5434/ght
#   REDIS_URL=redis://localhost:6380/0

# Infrastructure only — the API and frontend run on the host with hot reload.
docker compose up -d db redis

# Backend
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt
ln -sfn ../.env .env                      # one .env for the whole repo
./.venv/bin/alembic upgrade head
./.venv/bin/python -m app.db.seed         # prints the bootstrap password once
./.venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                               # http://localhost:5174
```

`http://localhost:5174` is already in the default `CORS_ORIGINS`.

| Service | URL |
| ------- | --- |
| Frontend (dev) | http://localhost:5174 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

## Layout

```
backend/app/
├── api/
│   ├── deps.py          auth + authorization dependencies  ← read this first
│   └── v1/              route modules
├── core/                config, database, redis, security, jwt, logging, errors
├── models/              SQLAlchemy models + enums
├── modules/registry.py  the tool catalogue
├── schemas/             Pydantic contracts
├── services/            business logic
│   └── permission_service.py   ← the only place permissions are decided
└── db/seed.py

frontend/src/
├── auth/                AuthContext + permission helpers
├── components/          Layout + UI primitives
├── lib/api.ts           fetch client, refresh coordination, CSRF
├── pages/
└── routes.tsx           route table and guards
```

## Testing

```bash
cd backend
docker compose -f ../docker-compose.yml up -d db redis    # required
./.venv/bin/pytest                    # full suite (~4 min)
./.venv/bin/pytest tests/test_auth.py -v
./.venv/bin/pytest -k "permission"
./.venv/bin/pytest --durations=10
```

The suite creates and migrates a separate `ght_test` database on each run, so
migrations are verified every time. Redis is disabled, which exercises the
in-process fallbacks.

| File | Covers |
| ---- | ------ |
| `test_auth.py` | Sign-in, lockout, sessions, rotation, reuse detection, password change, first-login enforcement, audit |
| `test_users.py` | Creation, duplicates, roles, status, escalation guards, admin reset |
| `test_authorization.py` | Level algebra, resolution, multi-role union, API enforcement, matrix editing |
| `test_password_reset.py` | Token generation, storage, expiry, reuse, session revocation |
| `test_security.py` | Hashing, policy, token primitives, redaction, rate limiting, headers, production config guards |
| `test_roles.py` | Role creation/editing/deletion, key derivation, protected system roles, escalation guards, custom roles in action |
| `test_dashboard_access.py` | Dashboard visibility per role, server-side enforcement, module registry integrity |

### Writing tests

Fixtures come from `tests/conftest.py`: `db`, `client`, `superadmin`, `admin`,
`normal_user`, `guest`, plus `login`, `auth_headers`, `create_user`, `refetch`
and `read_outbox_token`.

```python
async def test_guest_cannot_reach_user_admin(client, guest):
    headers = await auth_headers(client, guest.email, GUEST_PASSWORD)
    assert (await client.get("/api/v1/users", headers=headers)).status_code == 403
```

Two harness details worth knowing:

- The API writes through its own session, so use `refetch(db, Model, pk)` to
  re-read a row — a plain query returns the identity-mapped, stale object.
- Fixtures and tests share one event loop (asyncpg connections are bound to the
  loop that opened them), and the engine is per-test.

## Frontend

```bash
npm run dev         # dev server
npm run typecheck   # tsc --noEmit
npm run build       # production build
npm test            # vitest (31 tests)
npm run test:watch
```

TypeScript runs in strict mode with `noUncheckedIndexedAccess`. Keep it clean.

### Frontend tests

Vitest + Testing Library + jsdom. Configuration in `vitest.config.ts`; global
setup in `src/test/setup.ts`.

| File | Covers |
| ---- | ------ |
| `components/ui/Modal.test.tsx` | Focus stability — the regression guard for the Create User focus defect |
| `pages/access/CreateUserDialog.test.tsx` | The whole Create User workflow: typing, role selection, submission, errors |
| `auth/permissions.test.ts` | Access-level algebra, `accessibleModules`, route matching |
| `pages/DashboardPage.test.tsx` | Only authorized modules are rendered |

Two conventions worth keeping:

- **Test through user-visible behaviour** (`getByLabelText`, `userEvent`), not
  implementation details. The focus bug was only catchable this way.
- **Mock at the `@/lib/api` boundary**, never `fetch` — the client's refresh and
  CSRF handling should stay exercised by the real code paths in integration.

### A note on effects and focus

`Modal`'s focus effect depends on `open` **alone**. Adding anything that changes
per render — `onClose`, a config object, an inline array — makes it re-run on
every keystroke and steal focus from whatever the user is typing into. If you
need the latest value of such a prop inside an effect, hold it in a ref
(see `onCloseRef`) rather than adding it to the dependency array.

## Adding a new module

The platform is built so this is a small change.

**1. Register it** — `backend/app/modules/registry.py`:

```python
ModuleDefinition(
    key="TEAM_MEMBERS",
    name="Team Members",
    icon="\N{BUSTS IN SILHOUETTE}",
    route="/team-members",
    description="Directory of team members.",
    sort_order=20,
    is_implemented=True,          # flip when the real UI ships
    defaults=_defaults(),          # admin=COMPLETE, user=READ_ONLY, guest=GUEST
),
```

**2. Seed** — automatic on container start, or `python -m app.db.seed`.

At this point it already has a dashboard card, a sidebar entry, a guarded route
rendering the placeholder, and a row in the role permission matrix.

**3. Build the backend** — `app/api/v1/team_members.py`:

```python
router = APIRouter(prefix="/team-members", tags=["Team Members"])
MODULE = "TEAM_MEMBERS"

@router.get("", dependencies=[Depends(require_access(MODULE, ModuleAction.VIEW))])
async def list_members(db: DbSession): ...

@router.post("")
async def create_member(
    actor: Annotated[ActiveUser, Depends(require_access(MODULE, ModuleAction.CREATE))],
    db: DbSession,
): ...
```

Register it in `app/api/v1/router.py`. **Never** write your own permission
check — always `require_access`.

**4. Build the frontend** — add a page and map it in `src/routes.tsx` alongside
`ACCESS_MANAGEMENT` and `SETTINGS`. Use `can(permissionMap, MODULE, 'UPDATE')`
to hide write controls.

**5. Migrations** for any new tables:

```bash
./.venv/bin/alembic revision --autogenerate -m "add team member tables"
# review the generated file, then:
./.venv/bin/alembic upgrade head
```

**6. Tests** for the endpoints, including a denial case per role.

**7. Documentation** — update `PRIORITY.md`, `PROJECT_STATUS.md`,
`CHANGELOG.md`, and `docs/API.md`.

Once seeded, the new module also appears automatically in the role permission
matrix, so administrators can grant access to it without any further work.

## Adding a role

Roles are data, not code. Create one through the UI (Access Management →
Roles & permissions → Create role) or the API:

```bash
curl -X POST "$API/api/v1/roles" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{
    "name": "Asset Manager",
    "description": "Owns the hardware register.",
    "permissions": {"ASSET_INVENTORY": "COMPLETE", "ZABBIX": "READ_ONLY"}
  }'
```

Do **not** add roles to `app/modules/registry.py` unless they are part of the
platform foundation — that file seeds the four system roles, which are protected
from deletion. Everything else belongs in the database.

## Conventions

**Backend**

- Type hints everywhere; `from __future__ import annotations` at the top.
- Routes parse and delegate; business rules live in `services/`.
- Raise `AppError` subclasses, not bare `HTTPException` — the handler renders
  the standard envelope.
- Services do not commit; the route decides the transaction boundary.
- Never log a password or token. The filter will catch it, but do not rely on it.

**Frontend**

- Functional components with hooks; no class components.
- All API calls go through `lib/api.ts`.
- Permission checks go through `auth/permissions.ts` — never compare access
  level strings inline.
- Every async view renders loading, empty and error states.
- Label every form control; keep the focus ring visible.

## Development rules

1. Do not implement future modules prematurely.
2. Build reusable foundations.
3. Do not duplicate authorization logic. Use `require_access` server-side and
   `can()` client-side — never compare role names or access-level strings.
4. Do not hard-code permissions in UI components.
5. Keep secrets out of source control.
6. Use migrations for every schema change.
7. Update documentation when architecture changes.
8. Update `PROJECT_STATUS.md` after meaningful work.
9. Update `PRIORITY.md` when priorities change.
10. Update `CHANGELOG.md` for meaningful changes.
11. Write tests for security-sensitive functionality.
12. Do not claim something is implemented unless it is implemented and verified.
