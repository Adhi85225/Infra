# Architecture

## Goal

A **platform**, not an application. Roughly a dozen internal tools will be built
here over time. The parts they share — sign-in, permissions, audit, navigation —
are built once, and each tool plugs into them.

The organising constraint: **adding a tool must not require touching the
authentication or authorization code.**

## Shape

```
Browser
  │  HTTPS
  ▼
┌──────────────────────────┐
│ web  (nginx :8080)       │  React SPA, static assets
└──────────────────────────┘
  │  JSON over HTTPS  (Bearer access token + refresh cookie)
  ▼
┌──────────────────────────┐
│ api  (uvicorn :8000)     │  FastAPI
│                          │
│  api/      HTTP layer, auth & authorization dependencies
│  services/ business logic (single source of permission truth)
│  models/   SQLAlchemy ORM
│  core/     config, db, redis, security, logging, errors
│  modules/  the tool registry
└──────────────────────────┘
     │                    │
     ▼                    ▼
┌──────────┐        ┌──────────┐
│ postgres │        │  redis   │
│  :5432   │        │  :6379   │
└──────────┘        └──────────┘
 system of record   rate limits, permission
                    cache, token deny-list
```

Networks are split: `db` and `redis` sit on a `backend` network reachable only
by the API. `web` and `api` share a `frontend` network. The database is never
reachable from the browser-facing container.

## Layers, and what belongs in each

| Layer      | Responsibility                                            | Must not |
| ---------- | --------------------------------------------------------- | -------- |
| `api/`     | Parse, validate, declare access requirements, serialise    | Contain business rules or permission logic |
| `services/`| Business rules, permission resolution, audit writes        | Know about HTTP status codes |
| `models/`  | Schema and relationships                                   | Contain behaviour beyond trivial derived properties |
| `core/`    | Cross-cutting infrastructure                               | Import from `services/` or `api/` |
| `schemas/` | The wire contract                                          | Leak internal fields such as `password_hash` |

## The three ideas that make it modular

### 1. Modules are data

A tool is a row in `modules`. `app/modules/registry.py` is the code-side
catalogue that seeds those rows; at runtime the **database is authoritative**, so
an administrator can change a module's grants without a deployment.

Adding a tool:

1. Append a `ModuleDefinition` to the registry.
2. Run the seed (automatic on container start).

It now appears on the dashboard and in the sidebar, has a guarded route, and is
listed in the role permission matrix — with no changes to authorization code,
routing tables or navigation components.

### 2. Roles are data too

The four seeded roles are a starting point, not a fixed set. Administrators
create `AssetManager`, `ReportViewer`, `NetworkAdmin` and so on at runtime, each
with its own module permissions, and the resolver treats them identically to the
seeded ones. The only role property with meaning in code is `is_superuser`.

Seeded roles are flagged `is_system` and protected from deletion, so the
platform's own access model cannot be dismantled by accident.

### 3. One permission resolver

`app/services/permission_service.py` is the only place that decides what a user
may do:

```
if any role is_superuser  ->  COMPLETE on every active module
else                      ->  per module, the highest level any of the
                              user's roles grants (missing row = NONE)
inactive module           ->  NONE
```

Endpoints state a requirement and nothing more:

```python
@router.post("", dependencies=[Depends(require_access("ACCESS_MANAGEMENT", ModuleAction.CREATE))])
```

The frontend receives the resolved map and renders from it, so the UI cannot
drift from the server's answer: the dashboard shows only modules the user can
open, and the sidebar and route guards use the same helper.

**Server-side enforcement is the boundary.** Hiding a card or blocking a route
is convenience — a user who types the URL, or calls the API directly, is refused
by `require_access` either way. Permissions are never read from the request.

### 4. Auth is decoupled from tools

Nothing in the authentication layer knows any tool exists. Modules are
referenced by string key, resolved through the database. Swapping in SSO later
means replacing credential verification and session creation — the permission
model is untouched.

## Session design

| Token          | Lifetime | Stored where                    | Purpose |
| -------------- | -------- | ------------------------------- | ------- |
| Access (JWT)   | 15 min   | Browser memory only             | Authenticates API calls via `Authorization` |
| Refresh (opaque) | 7 days | httpOnly cookie; SHA-256 digest in the database | Obtains new access tokens |
| CSRF           | 7 days   | Readable cookie                 | Echoed in a header on cookie-authenticated calls |

Why this split:

- A token in `localStorage` survives a reload and is readable by any injected
  script. Keeping the access token in memory limits exfiltration to the current
  page context.
- The refresh token is the durable credential, so it is kept where JavaScript
  cannot read it at all.
- Because normal API calls authenticate with a header rather than a cookie, they
  are not CSRF-reachable. CSRF protection is therefore applied to exactly the
  two endpoints that do authenticate by cookie.

Refresh tokens **rotate**: each use revokes the presented token and issues a
successor linked to it. Presenting an already-rotated token means someone has a
copy, so the entire session family is revoked.

Every request re-reads the user and session from the database — a deactivated
account or a revoked session stops working immediately rather than at token
expiry.

## Redis: useful, not required

Redis holds rate-limit counters, a 60-second permission cache and the
access-token deny-list. If it is unreachable the application keeps serving:
limits fall back to per-process counters and permissions are recomputed per
request. The trade-off is explicit — a multi-node deployment needs Redis for
limits to be global, and the deny-list is an optimisation on top of the
per-request database check, not the mechanism itself.

## Errors

Every failure leaves the API in one envelope:

```json
{"error": {"code": "invalid_credentials", "message": "…", "details": {}}}
```

Clients branch on `code`; `message` is safe to show a user. Unhandled exceptions
are logged with a stack trace and returned as a generic `internal_error`.

## Logging

Structured JSON on stdout. A process-wide filter redacts passwords, tokens and
authorization headers from **every** logger, including third-party ones. Domain
context is passed via `extra` and sanitised so it can never shadow core fields
or collide with reserved `LogRecord` attributes.

## Rejected alternatives

| Considered | Why not |
| ---------- | ------- |
| Roles as a string column on `users` | Cannot express multiple roles or query permissions; explicitly ruled out by the requirements |
| Permissions hard-coded in a Python dict | Changing a rule would need a deployment; the requirement was runtime configurability |
| Server-side sessions in Redis only | Makes Redis a hard dependency for authentication; the database already needs to be consulted per request |
| Access token in a cookie | Puts the entire API behind CSRF instead of two endpoints |
| A separate service per module | Enormous operational cost for an internal tool set; a modular monolith splits later if it ever needs to |
| Passlib for hashing | Extra layer over `argon2-cffi` with a history of version-compatibility friction |
