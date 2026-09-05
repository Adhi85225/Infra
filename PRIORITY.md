# Application Development Priorities

The prioritised roadmap for Global Infrastructure. **This file is authoritative
for what gets built next.** Update it whenever priorities change.

Status key: ✅ done and verified · 🚧 in progress · ⬜ not started

Nothing is marked ✅ unless it is implemented **and** covered by a passing test
or a documented manual verification.

---

## P0 — Foundation  ✅ COMPLETE (Phase 1)

| Item                            | Status | Notes                                            |
| ------------------------------- | ------ | ------------------------------------------------ |
| Project setup & structure       | ✅     | FastAPI + React monorepo                         |
| Database schema & migrations    | ✅     | PostgreSQL 16, Alembic, 9 tables                 |
| Authentication (email + password) | ✅   | JWT access + rotating refresh cookie             |
| Session management              | ✅     | Rotation, reuse detection, revocation            |
| Authorization architecture      | ✅     | Central permission service, no scattered checks  |
| Roles (SuperAdmin/Admin/User/Guest) | ✅ | Relational, many-to-many, extensible             |
| Multiple roles per user         | ✅     | Effective access = highest level across roles    |
| Module-level permissions        | ✅     | `Role × Module → AccessLevel`, editable at runtime |
| User management (admin)         | ✅     | Create, edit, status, roles, admin reset         |
| First-login password change     | ✅     | Enforced server-side on every endpoint           |
| Password change                 | ✅     | Policy, history, session revocation              |
| Forgot / reset password         | ✅     | Hashed, single-use, expiring tokens              |
| SMTP configuration structure    | ✅     | Config + transport seam; delivery intentionally unimplemented |
| Audit log foundation            | ✅     | 16 action types, extensible                      |
| Dashboard with tool placeholders | ✅    | Generated from the permission map                |
| Rate limiting                   | ✅     | Redis-backed, per-client                         |
| Docker + Docker Compose         | ✅     | 4 services, health checks, auto-migrate          |
| Documentation                   | ✅     | `docs/` + PRIORITY / STATUS / CHANGELOG          |
| Automated tests                 | ✅     | 260 passing (229 backend, 31 frontend)           |

### P0 — Role management & dashboard authorization ✅ COMPLETE

Treated as P0 because it changes the authentication/authorization foundation.

| Item                                  | Status | Notes                                                   |
| ------------------------------------- | ------ | ------------------------------------------------------- |
| Create custom roles                   | ✅     | `POST /roles`; keys derived from the name               |
| Edit / view / delete roles            | ✅     | System roles protected; in-use roles refused            |
| Module permissions per role           | ✅     | Complete / Read Only / No Access, editable at runtime   |
| Role Management UI                    | ✅     | Access Management → Roles & permissions                 |
| Dashboard shows only authorized tools | ✅     | Filtered by effective permissions across all roles      |
| Server-side authorization             | ✅     | `require_access` on every protected endpoint            |
| Route protection                      | ✅     | Forbidden page for unauthorized module URLs             |
| Escalation guards                     | ✅     | No self-assignment; no granting beyond your own access  |
| Create User focus defect              | ✅     | Root cause fixed in `Modal.tsx`; regression tests added |
| Multiple roles at user creation       | ✅     | Verified end-to-end                                     |
| Frontend test infrastructure          | ✅     | Vitest + Testing Library, 31 tests                      |

---

## P1 — Core Administration  ⬜ NEXT

The immediate priority once Phase 1 is signed off.

| Item                            | Status | Notes                                              |
| ------------------------------- | ------ | -------------------------------------------------- |
| **Real SMTP delivery**          | ⬜     | Highest priority: temporary passwords and reset links are currently handed over manually. See `docs/SMTP.md` |
| **Decide the `USER` permission matrix** | ⬜ | Currently `READ_ONLY` on Access Management, so a plain user can list users and roles. A seeded default, not a bug — but it needs a deliberate decision. Changeable in the UI |
| Team Members module             | ⬜     | First real tool; the directory the org actually needs |
| Admin Settings module           | ⬜     | Editable configuration surface                     |
| Audit log filtering & export    | ⬜     | Read API exists and the UI lists entries; needs richer query + CSV |
| Bulk role assignment            | ⬜     | Assign a role to many users at once                |
| Reassign-then-delete for roles  | ⬜     | Today an in-use role must be cleared manually first |
| User profile self-service       | ⬜     | Let users edit their own profile fields            |
| Bulk user import                | ⬜     | CSV onboarding for larger teams                    |

## P2 — Infrastructure Tools  ⬜

Each is an independent module built on the existing core.

| Item              | Status | Notes                                    |
| ----------------- | ------ | ---------------------------------------- |
| Asset Inventory   | ⬜     | Hardware/software register               |
| DAS Onboarding    | ⬜     | Onboarding workflow                      |
| ILO Inventory     | ⬜     | Lights-out management inventory          |
| Zabbix            | ⬜     | Read-only integration first              |
| Nexus             | ⬜     | Repository/artifact information          |
| Cloud Information | ⬜     | Multi-cloud resource and spend overview  |

## P3 — Operations  ⬜

| Item          | Status | Notes                              |
| ------------- | ------ | ---------------------------------- |
| Task Updates  | ⬜     | Team task tracking                 |
| Manager Reports | ⬜   | Reporting for team leads           |
| Admin Reports | ⬜     | Platform-wide reporting            |

## P4 — Future  ⬜

| Item                          | Status | Notes                                        |
| ----------------------------- | ------ | -------------------------------------------- |
| SSO / OIDC                    | ⬜     | The auth layer is deliberately decoupled     |
| Two-factor authentication     | ⬜     | TOTP; the session model already supports it  |
| Per-user permission overrides | ⬜     | Resolver is designed to accept another grant source alongside roles |
| Role templates / cloning      | ⬜     | "Create a role like this one" for large matrices |
| Notifications                 | ⬜     | Needs SMTP first                             |
| Background jobs               | ⬜     | Redis is already in the stack                |
| Observability (metrics/traces) | ⬜    | Structured logging is in place               |

---

## Standing engineering priorities

These outrank new features when they conflict:

1. **Security correctness** — no shortcuts for speed.
2. **One authorization path** — never re-implement permission logic locally.
3. **Migrations for every schema change** — no manual DDL.
4. **Tests for security-sensitive code** — auth, authz, tokens.
5. **Documentation stays truthful** — update it in the same change.

_Last updated: 2026-09-04_
