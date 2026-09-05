# Changelog

All notable changes to this project are recorded here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

**Role management & dashboard authorization**

_Roles_
- Administrators can create custom roles at runtime (`POST /roles`) with their
  own module permissions — `AssetManager`, `ReportViewer`, `NetworkAdmin` and so
  on — with no code change and no deployment.
- Roles can be renamed and described (`PATCH /roles/{id}`), re-permissioned
  (`PUT /roles/{id}/permissions`) and deleted (`DELETE /roles/{id}`).
- Machine keys are derived from the display name (`"Asset Manager"` →
  `ASSET_MANAGER`) or supplied explicitly, and are immutable thereafter.
- `GET /roles` now reports `user_count` and `is_deletable` per role.
- `GET /roles/assignable-access-levels` publishes the assignable levels so the
  UI never hard-codes them.
- The four seeded roles are protected: they cannot be deleted or re-keyed, and
  Super Admin's computed permissions cannot be edited.
- A role still assigned to users cannot be deleted (`409 role_in_use`).

_Role Management UI_
- Access Management → **Roles & permissions**: list with holder counts and
  role type, create/edit dialog with the full module matrix, read-only detail
  view, and a delete confirmation that warns when a role is in use.
- Built entirely from the existing Modal, Button, Field, Badge, Alert, table and
  toast components — no separate visual system.

_Dashboard authorization_
- The dashboard now renders **only** the modules the user can open. A module
  resolving to `NONE` is not shown at all, rather than shown locked.
- The sidebar and dashboard share one `accessibleModules()` helper.
- Visibility is computed from effective permissions across every assigned role.

_Frontend testing_
- Vitest + Testing Library + jsdom, with 31 tests covering the Create User
  workflow, permission helpers and dashboard filtering.

**Phase 1 — Authentication & Access Foundation**

_Project foundation_
- FastAPI backend (Python 3.12, SQLAlchemy 2 async, Pydantic v2, Alembic).
- React 18 + TypeScript + Vite + Tailwind frontend.
- PostgreSQL 16 and Redis 7 services.
- Docker Compose stack with health checks and automatic migration/seeding.

_Database_
- Initial migration `0001_initial`: `users`, `roles`, `user_roles`, `modules`,
  `role_module_permissions`, `sessions`, `password_reset_tokens`,
  `password_history`, `audit_logs`.
- Idempotent seed for roles, the module catalogue, default permissions and a
  bootstrap Super Admin.

_Authentication_
- Email/password sign-in, logout and `/auth/me`.
- JWT access tokens plus opaque rotating refresh tokens in an httpOnly cookie.
- Refresh-token reuse detection with session-family revocation.
- Account lockout after repeated failed sign-ins.
- Mandatory first-login password change, enforced server-side.
- Password change with policy, history and session revocation.
- Forgot/reset password with hashed, single-use, expiring tokens.
- Password policy published at `/auth/password-policy` so the UI never
  duplicates the rules.

_Authorization_
- Roles: SuperAdmin, Admin, User, Guest — many-to-many with users.
- Module access levels NONE / GUEST / READ_ONLY / COMPLETE, stored per role and
  editable at runtime.
- Central permission service resolving effective access as the highest level
  across a user's roles.
- `require_access(module, action)` dependency as the only way an endpoint
  expresses an access requirement.
- Privilege-escalation guards around SuperAdmin and self-modification.

_Administration_
- User CRUD, role assignment, status changes and admin password reset.
- Role permission matrix editor.
- Audit log with 16 action types and a read API.

_Frontend_
- Sign-in, forgot password, reset password, forced password change.
- Dashboard with permission-aware module cards.
- Access Management: users, role matrix, audit log.
- Sidebar, routes and cards all generated from the server's permission map.
- Loading, empty and error states; accessible forms and dialogs; toasts.

_Platform_
- Module registry so a new tool needs no authorization or routing changes.
- Redis-backed rate limiting with an in-process fallback.
- Structured JSON logging with mandatory secret redaction.
- Health and readiness probes.

_Email_
- Transport abstraction with a logging transport and a developer outbox.
- Full SMTP configuration surface; real delivery intentionally not implemented.

_Testing_
- 158 tests covering authentication, users, authorization, password reset and
  security primitives, run against a real PostgreSQL database with migrations
  applied.

_Documentation_
- `docs/`: ARCHITECTURE, REQUIREMENTS, DATABASE, AUTHENTICATION, AUTHORIZATION,
  API, ROUTES, SMTP, DEPLOYMENT, ENVIRONMENT, SECURITY, DEVELOPMENT, ROADMAP.
- `PRIORITY.md`, `PROJECT_STATUS.md`, `CHANGELOG.md`, `.env.example`.

### Changed
- **`GUEST` access level retired.** It permitted exactly the same action as
  `READ_ONLY` and only added an intermediate rank. Guest access is now expressed
  through ordinary effective permissions — the Guest *role* holding `READ_ONLY`
  grants — so role configuration offers the three levels operators reason about:
  No access / Read only / Complete. Migration `0002_guest_access` converts
  existing rows; no access is widened or narrowed. The enum value is retained so
  pre-migration rows still load.
- Roles are re-seeded per test and the whole catalogue is reset between tests,
  making the suite hermetic now that tests create roles and mutate modules.

### Security
- **Nobody may change their own roles** (`403 self_role_change_denied`).
  Self-assignment is the most direct privilege-escalation path; a second
  administrator is now required. This replaces the narrower rule that only
  prevented a Super Admin from removing their own Super Admin role.
- **Nobody may grant a role more access than they hold themselves.** Without
  this, any holder of `COMPLETE` on Access Management could mint an
  all-powerful role and assign it to a confederate. Super Admin is exempt, as it
  already holds everything.
- Module keys are validated before the escalation guard runs, so a typo reports
  "no such module" rather than a misleading permission error.
- Argon2id password hashing with OWASP-aligned, configuration-driven cost, and
  production floor checks at startup.
- Refresh and reset tokens persisted only as SHA-256 digests.
- Account-enumeration resistance on sign-in and forgot-password.
- Double-submit CSRF protection on cookie-authenticated endpoints.
- Security response headers; strict CORS; secrets sourced only from the
  environment.
- Logging filter that redacts passwords and tokens process-wide.
- Startup refuses insecure production configuration (default secret, insecure
  cookies, debug mode, weak hash cost).

### Fixed
- **Create User modal lost input focus.** `Modal`'s "focus the panel on open"
  effect listed `onClose` in its dependency array. Callers pass an inline arrow
  function, so `onClose` had a new identity on every render — and the dialog's
  own state updates re-rendered its parent on every keystroke. The effect
  therefore re-ran constantly and called `panel.focus()`, pulling focus out of
  the field being typed into; only the first character of any input survived.
  The focus effect is now keyed on `open` alone, with the latest `onClose` held
  in a ref for the Escape handler, and it focuses the first real control so the
  form is immediately usable. Contributing factors also fixed: `UsersTab` passed
  freshly-created callback props on every render (now `useCallback`), and
  refetched the role list on every search keystroke, giving the `roles` prop a
  new identity each time (now fetched once).
- **Role endpoints crashed after commit** (`MissingGreenlet`). `get_role_matrix`
  read grants through the `role.module_permissions` relationship, which
  `commit()`/`refresh()` expires; touching an expired lazy attribute under
  asyncio raises. Grants are now queried explicitly.

_Issues found and resolved during the initial Phase 1 build:_
- Rate-limit dependency implemented as a callable class could not resolve its
  type hints (a class instance has no `__globals__`), so FastAPI treated
  `Request` as a query parameter and every rate-limited route returned 422.
  Converted to a dependency factory.
- A session revoked by logout remained usable by an access token minted before
  a rotation, because the `rotated` revocation reason was treated as benign.
  Any revoked session now invalidates its access token.
- `PostgreSQL INET` values are returned by asyncpg as `ipaddress` objects and
  failed audit-log serialisation with a 500. Coerced in the schema, with a
  regression test.
- Log `extra` fields collided with reserved `LogRecord` attributes (`module`),
  raising `KeyError` mid-request; a logging adapter now renames them, and core
  fields can no longer be shadowed by caller context.
- The redaction filter stripped reset tokens from the log, making the Phase 1
  log transport unusable for development. Added a developer outbox that is
  disabled in production, rather than weakening redaction.

[Unreleased]: https://example.internal/global-infrastructure
