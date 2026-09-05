# Project Status

## Current Phase

**Phase 1 — Authentication & Access Foundation**

## Overall Status

✅ **Complete**, including the follow-up round of fixes and role-management
work. The application builds, starts, and has been verified end-to-end both
locally and through Docker Compose.

## Current Work

Nothing is in flight. The most recent round delivered:

- ✅ Fixed the Create User modal focus defect (root cause, with regression tests)
- ✅ Implemented role management — create, edit, view and delete custom roles
- ✅ Implemented module-level permissions for custom roles
- ✅ Made the dashboard permission-aware (only authorized modules are shown)
- ✅ Hardened role assignment against privilege escalation

The next unit of work is P1 in [PRIORITY.md](PRIORITY.md), led by
**real SMTP delivery**.

## Completed

**Authentication**
- Email + password sign-in; logout; identical responses for unknown-email and
  wrong-password so accounts cannot be enumerated.
- Short-lived JWT access tokens, opaque **rotating** refresh tokens in an
  httpOnly cookie, stored as SHA-256 digests.
- Refresh-token reuse detection: replaying a rotated token revokes the whole
  session family.
- Account status handling (ACTIVE / INACTIVE / SUSPENDED) re-checked on every
  request, so deactivating a user ends their live session immediately.
- Account lockout after repeated failures.
- First-login password change, enforced server-side across every endpoint.
- Password change with policy, reuse history and session revocation.
- Forgot/reset password with single-use, time-limited, hashed tokens.

**Role management** _(added after the initial Phase 1 build)_
- Administrators create custom roles (`AssetManager`, `ReportViewer`, …) with
  their own module permissions, at runtime, with no code change.
- Machine keys are derived from the name (`"Asset Manager"` → `ASSET_MANAGER`)
  and are immutable once set.
- Roles can be renamed, described, re-permissioned and deleted; the four seeded
  roles are flagged `is_system` and protected from deletion.
- Three assignable access levels — No access / Read only / Complete — published
  by the API so the UI never hard-codes them.
- The deprecated `GUEST` access level was retired by migration `0002`: guest
  access is now an ordinary `READ_ONLY` grant on the Guest role rather than a
  special case in the authorization model.
- Role Management UI lives under Access Management → Roles & permissions,
  reusing the existing dialog, table, toast and form components.

**Dashboard authorization**
- The dashboard renders only the modules the user can actually open; a module
  resolving to `NONE` is not advertised at all.
- Visibility is computed from effective permissions across every assigned role.
- The sidebar and the dashboard share one helper, so they cannot disagree.
- Direct URL navigation to an unauthorized module renders the Forbidden page,
  and the corresponding API calls are refused server-side.

**Authorization**
- Four seeded roles plus any number of custom ones; users may hold any number.
- `Role × Module → AccessLevel` (NONE / GUEST / READ_ONLY / COMPLETE) stored in
  the database and editable at runtime through the UI.
- Effective access = the highest level across a user's roles, resolved in one
  service (`app/services/permission_service.py`) that every check goes through.
- SuperAdmin resolves to COMPLETE implicitly, so it covers modules that do not
  exist yet.
- Enforcement is server-side; the UI renders from the same map.

**Administration**
- Admin user creation with a generated temporary password and forced change.
- Role assignment, profile/status editing, admin-triggered password reset.
- Privilege-escalation guards: nobody may change their own roles; nobody may
  grant a role more access than they hold themselves; only a SuperAdmin can
  grant SuperAdmin or modify a SuperAdmin; nobody may change their own account
  status; system roles cannot be deleted; a role still in use cannot be deleted.
- Audit log covering 16 action types, with redaction before persistence.

**Platform**
- Module registry: adding a tool is a registry entry + seed run, with no
  authorization or routing changes.
- Dashboard, sidebar and routes all generated from the permission map.
- Docker Compose stack (PostgreSQL, Redis, API, web) with health checks and
  automatic migration + seeding on start.
- 260 automated tests (229 backend, 31 frontend), all passing.
- Full documentation set.

## In Progress

_Nothing._

## Blocked

_Nothing._

## Next Steps

1. **Implement SMTP delivery** (`SMTPTransport.send`) — until then, temporary
   passwords and reset links must be handed over manually. See
   [docs/SMTP.md](docs/SMTP.md).
2. **Decide the `USER` role's real permission matrix.** It currently grants
   `READ_ONLY` on Access Management, so a plain user can list users and roles.
   That is a seeded default, not a bug, and is changeable in the UI with no
   deployment — but it should be a deliberate decision.
3. Build the **Team Members** module as the first real tool, following
   [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#adding-a-new-module).
4. Add audit-log filtering and export.

## Known Issues

None open. Accepted limitations (deliberate, documented in
[docs/SECURITY.md](docs/SECURITY.md)):

| Limitation | Why it is acceptable |
| ---------- | -------------------- |
| Email is not actually delivered | Explicitly out of scope for Phase 1; the seam and config exist |
| Access-token revocation needs Redis; without it a revoked token stays valid until it expires (≤15 min) | Sessions are still checked against the database on every request, so revocation is effective — only the deny-list optimisation degrades |
| A locked account reports `account_locked` before the password is verified | Reveals that an address exists, but is required for lockout to save the hashing work; rate limiting bounds the exposure |
| No per-user permission overrides | Not required by Phase 1; the resolver is structured to accept another source later |
| `USER` role permissions are placeholders | The requirements defer them to a later phase; runtime-configurable, and raised under Next Steps |
| Custom roles cannot be deleted while assigned | Deliberate: deleting would silently strip access. Reassign the holders first |
| Role machine keys are immutable | Keys appear in audit records and permission rows; renaming one would break that history. The display name is freely editable |

## Decisions Made

| Decision | Rationale |
| -------- | --------- |
| FastAPI + React + PostgreSQL + Redis | Requested stack |
| Access token in memory, refresh token in httpOnly cookie | A token in `localStorage` survives reload and is XSS-exfiltratable; this pair removes that while keeping refresh out of JS reach |
| Refresh rotation with family revocation | Standard, detectable response to token theft |
| Double-submit CSRF on cookie endpoints only | The Bearer-authenticated API is not CSRF-reachable, so protection is applied exactly where it is needed |
| Argon2id, parameters from configuration | OWASP first choice; configurable so tests are fast without weakening production, which is floor-checked at startup |
| Permissions in the database, not in code | "Change permissions later without restructuring" was a hard requirement |
| Module catalogue as data with a code registry seed | One place to add a tool; the database stays authoritative at runtime |
| Redis optional, with in-process fallback | A single-node deployment stays correct if Redis is briefly unavailable |
| Dev email outbox on disk | Logs redact tokens by design, so reset links could not be recovered from them; the outbox is disabled in production |
| Full module list returned by the API, filtered in the UI | The client needs a module's route to render a Forbidden page for a direct URL. The dashboard and sidebar filter to accessible modules; the API refuses the rest regardless |
| Roles as ordinary data rows, not code | "Add roles without code changes" was the explicit requirement |
| Nobody may change their own roles | Self-assignment is the most direct escalation path; requiring a second administrator is a small cost |
| Nobody may grant beyond their own access | Closes the escalation route where a user with only Access Management could mint an all-powerful role |
| `GUEST` access level retired, enum value kept | The level added a rank but no distinct capability. Keeping the value means pre-migration rows still load |

## Verification

| Check | Result |
| ----- | ------ |
| `pytest` (backend) | ✅ 229 passed |
| `vitest` (frontend) | ✅ 31 passed |
| `tsc --noEmit` (frontend) | ✅ no errors |
| `npm run build` | ✅ builds |
| `docker compose up -d --build` | ✅ all 4 services healthy |
| Migrations from an empty database | ✅ applied by the entrypoint |
| Bootstrap admin sign-in → forced change → admin actions | ✅ verified in the container stack |
| Guest/User/Admin/SuperAdmin permission enforcement | ✅ covered by tests and manual checks |
| Custom role created, assigned, dashboard filtered, API refused | ✅ verified in the container stack |
| Create User modal focus and value retention | ✅ regression tests reproduce the old failure |
| Migration `0002` from an existing database | ✅ applied without data loss |

## Last Updated

2026-09-04
