# Routes & URLs

Every URL in the system. Base URLs come from configuration:

| Placeholder | Default (local Docker) | Variable |
| ----------- | ---------------------- | -------- |
| `{WEB}` | `http://localhost:8080` | `FRONTEND_BASE_URL` / `WEB_PORT` |
| `{API}` | `http://localhost:8000` | `VITE_API_BASE_URL` / `API_PORT` |

## Frontend routes

### Public (no session required)

| Route | Page | Notes |
| ----- | ---- | ----- |
| `{WEB}/login` | Sign in | Email + password |
| `{WEB}/forgot-password` | Request a reset link | Always reports success |
| `{WEB}/reset-password?token=…` | Set a new password | **The link sent by email** |

### Authenticated

| Route | Page | Module permission |
| ----- | ---- | ----------------- |
| `{WEB}/change-password` | Forced first-login change | none — reachable while a change is pending |
| `{WEB}/account/password` | Voluntary password change | none |
| `{WEB}/dashboard` | Tool cards | `DASHBOARD` VIEW |
| `{WEB}/access-management` | Users · Roles & permissions · Audit log | `ACCESS_MANAGEMENT` VIEW |
| `{WEB}/settings` | Settings | `SETTINGS` VIEW |

### Module placeholders (Phase 1)

Each requires VIEW on its module and renders the placeholder page.

| Route | Module key |
| ----- | ---------- |
| `{WEB}/team-members` | `TEAM_MEMBERS` |
| `{WEB}/asset-inventory` | `ASSET_INVENTORY` |
| `{WEB}/das-onboarding` | `DAS_ONBOARDING` |
| `{WEB}/ilo-inventory` | `ILO_INVENTORY` |
| `{WEB}/zabbix` | `ZABBIX` |
| `{WEB}/nexus` | `NEXUS` |
| `{WEB}/cloud-information` | `CLOUD_INFORMATION` |
| `{WEB}/task-updates` | `TASK_UPDATES` |
| `{WEB}/reports` | `REPORTS` |

Routes are generated from the module catalogue, so a new module gets its route
automatically.

A user without VIEW on a module gets the **Forbidden** page when navigating to
its URL directly, and the corresponding API calls are refused with `403`. Route
guarding is convenience; the API is the boundary.

## API endpoints

Prefix: `{API}/api/v1`

### Health (public)

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `{API}/health` | Liveness |
| GET | `{API}/health/ready` | Readiness — checks database and Redis |

### Authentication

| Method | Path | Auth | Rate limit |
| ------ | ---- | ---- | ---------- |
| POST | `/auth/login` | none | `RATE_LIMIT_LOGIN` |
| POST | `/auth/refresh` | refresh cookie + CSRF header | — |
| POST | `/auth/logout` | cookie + CSRF header (bearer optional) | — |
| GET | `/auth/me` | bearer | — |
| POST | `/auth/change-password` | bearer | — |
| POST | `/auth/forgot-password` | none | `RATE_LIMIT_FORGOT_PASSWORD` |
| POST | `/auth/reset-password` | none | `RATE_LIMIT_RESET_PASSWORD` |
| GET | `/auth/password-policy` | none | — |

### Users — module `ACCESS_MANAGEMENT`

| Method | Path | Required action |
| ------ | ---- | --------------- |
| GET | `/users` | VIEW |
| GET | `/users/{user_id}` | VIEW |
| POST | `/users` | CREATE |
| PATCH | `/users/{user_id}` | UPDATE |
| PUT | `/users/{user_id}/roles` | UPDATE |
| POST | `/users/{user_id}/reset-password` | UPDATE |

### Roles & modules — module `ACCESS_MANAGEMENT`

| Method | Path | Required action |
| ------ | ---- | --------------- |
| GET | `/roles` | VIEW |
| GET | `/roles/assignable-access-levels` | VIEW |
| GET | `/roles/{role_id}` | VIEW |
| POST | `/roles` | CREATE |
| PATCH | `/roles/{role_id}` | UPDATE |
| DELETE | `/roles/{role_id}` | UPDATE |
| PUT | `/roles/{role_id}/permissions` | UPDATE |
| GET | `/modules` | VIEW |

### Audit — module `ACCESS_MANAGEMENT`

| Method | Path | Required action |
| ------ | ---- | --------------- |
| GET | `/audit-logs` | VIEW |

### Interactive documentation

Available outside production only (disabled when `ENVIRONMENT=production`):

| URL | |
| --- | --- |
| `{API}/docs` | Swagger UI |
| `{API}/redoc` | ReDoc |
| `{API}/openapi.json` | OpenAPI schema |

## Cookies

| Name | Flags | Path | Purpose |
| ---- | ----- | ---- | ------- |
| `ght_refresh` | HttpOnly, SameSite, Secure in production | `/api/v1/auth` | Refresh credential |
| `ght_csrf` | readable by JS, SameSite | `/` | Echoed in `X-CSRF-Token` |
