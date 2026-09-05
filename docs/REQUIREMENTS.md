# Requirements Traceability

Every Phase 1 requirement, where it is implemented, and how it is verified.

Status: ✅ implemented and verified · ⚠️ intentionally partial · ⬜ not started

---

## Core requirements

| # | Requirement | Status | Implementation | Verified by |
|---|-------------|--------|----------------|-------------|
| 1 | Email-based login | ✅ | `api/v1/auth.py::login`, `services/auth_service.py::authenticate` | `test_auth.py::TestLogin` |
| 2 | User creation (admin only) | ✅ | `api/v1/users.py::create_user`, `services/user_service.py::create_user` | `test_users.py::TestCreateUser` |
| 3 | User roles | ✅ | `models/user.py::Role`, seeded from `modules/registry.py` | `test_authorization.py::TestPermissionResolution` |
| 4 | Multiple roles per user | ✅ | `models/user.py::UserRole` (M:N), `permission_service.highest()` | `test_authorization.py::test_multiple_roles_take_the_highest_level` |
| 5 | Module/tool-level access control | ✅ | `models/permission.py::RoleModulePermission`, `api/deps.py::require_access` | `test_authorization.py::TestPermissionsOverTheApi` |
| 6 | First-login password change | ✅ | `User.must_change_password`, `api/deps.py::get_active_user` | `test_auth.py::TestFirstLoginPasswordChange` |
| 7 | Forgot password | ✅ | `auth_service.request_password_reset` / `reset_password` | `test_password_reset.py` |
| 8 | Change password | ✅ | `auth_service.change_password` | `test_auth.py::TestChangePassword` |
| 9 | SMTP configuration structure | ✅ | `core/config.py::SMTPSettings`, `services/email/` | `docs/SMTP.md`; transport selection exercised by the reset tests |
| 10 | Dashboard with tool placeholders | ✅ | `pages/DashboardPage.tsx`, `pages/ModulePlaceholderPage.tsx` | Manual: 12 cards render, locked cards disabled |
| 11 | Docker deployment | ✅ | `backend/Dockerfile`, `frontend/Dockerfile` | `docker compose build` |
| 12 | Docker Compose | ✅ | `docker-compose.yml` | All four services report healthy |
| 13 | Complete documentation | ✅ | `docs/` (13 documents) | This file |
| 14 | Development/progress tracking | ✅ | `PRIORITY.md`, `PROJECT_STATUS.md`, `CHANGELOG.md` | — |

## Roles

| Role | Status | Implementation | Verified by |
|------|--------|----------------|-------------|
| SuperAdmin | ✅ | `Role.is_superuser`; resolution short-circuits to COMPLETE | `test_authorization.py::test_superadmin_gets_complete_on_everything` |
| Admin | ✅ | Seeded with COMPLETE on all modules | `test_authorization.py::test_admin_defaults` |
| User | ⚠️ | Seeded READ_ONLY (SETTINGS = NONE) | `test_authorization.py::test_user_defaults` |
| Guest | ✅ | Seeded READ_ONLY (ACCESS_MANAGEMENT, SETTINGS = NONE) | `test_authorization.py::test_guest_defaults` |
| **Custom roles** | ✅ | Created at runtime via `POST /roles` | `test_roles.py::TestCreateRole` |

⚠️ `USER` permissions are a **documented placeholder** — the requirements defer
the exact matrix to a later phase. They are editable at runtime.

## Role management

| Requirement | Status | Implementation | Verified by |
|-------------|--------|----------------|-------------|
| View existing roles | ✅ | `GET /roles`, `RolesTab.tsx` | `test_roles.py` |
| Create a new role | ✅ | `POST /roles`, `role_service.create_role` | `TestCreateRole` |
| Define role name | ✅ | `RoleCreate.name` | `test_admin_can_create_a_custom_role` |
| Define description | ✅ | `RoleCreate.description` | `TestEditRole` |
| Configure module permissions | ✅ | `RoleCreate.permissions`, `PUT /roles/{id}/permissions` | `test_permissions_are_stored_as_given` |
| Save the role | ✅ | `POST /roles` | `TestCreateRole` |
| Edit roles | ✅ | `PATCH /roles/{id}` | `TestEditRole` |
| View role details | ✅ | `GET /roles/{id}`, detail dialog | `test_the_key_is_immutable` |
| Delete custom roles | ✅ | `DELETE /roles/{id}` | `TestDeleteRole` |
| Roles not hard-coded | ✅ | `roles` table; only `is_superuser` has code meaning | `test_a_new_role_needs_no_deployment` |
| Seeded roles remain | ✅ | `registry.ROLE_DEFINITIONS` | `test_the_four_seeded_roles_still_exist` |
| System roles protected | ✅ | `PROTECTED_ROLE_KEYS`, `is_system` | `TestProtectedSystemRoles` |
| Complete / Read Only / No Access | ✅ | `ASSIGNABLE_ACCESS_LEVELS` | `test_the_api_publishes_the_assignable_levels` |
| Extensible permission model | ✅ | `role_module_permissions` rows | `TestCustomRoleInAction` |

## Dashboard authorization

| Requirement | Status | Implementation | Verified by |
|-------------|--------|----------------|-------------|
| Dashboard shows only authorized modules | ✅ | `accessibleModules()` in `DashboardPage.tsx` | `DashboardPage.test.tsx`, `test_dashboard_access.py::TestDashboardVisibility` |
| Filtering uses effective permissions | ✅ | `permission_service.resolve_permissions` | `test_custom_role_sees_exactly_its_grants` |
| Works with multiple roles | ✅ | `highest()` across all roles | `test_multiple_roles_union_their_visibility` |
| Unauthorized URLs blocked | ✅ | `RequireModule` → Forbidden page | `permissions.test.ts::moduleForRoute` |
| Unauthorized APIs blocked | ✅ | `require_access` dependency | `test_dashboard_access.py::TestServerSideEnforcement` |
| Permissions never trusted from client | ✅ | Resolved server-side per request | `test_the_client_cannot_supply_its_own_permissions` |
| Centralized resolution | ✅ | One service; `can()/canView()/canManage()` on the client | Whole `test_authorization.py` |
| Module registry, no duplication | ✅ | `app/modules/registry.py` | `test_dashboard_access.py::TestModuleRegistry` |

## Create User modal (focus defect)

| Requirement | Status | Implementation | Verified by |
|-------------|--------|----------------|-------------|
| Focus remains stable | ✅ | `Modal.tsx` focus effect keyed on `open` alone | `Modal.test.tsx`, `CreateUserDialog.test.tsx` |
| Buttons do not reset the form | ✅ | Local state untouched by re-render | `test: keeps entered values when roles are selected` |
| Role selection does not remount | ✅ | Stable `onClose`/`onCreated` via `useCallback` | `test: keeps entered values when the parent re-renders` |
| Entered values retained | ✅ | Controlled inputs, no remount | `test: retains values when moving between fields` |
| Modal stays open until dismissed | ✅ | `open` driven only by explicit actions | `test: stays open until the user explicitly cancels` |
| Multiple roles assignable | ✅ | Checkbox set → `role_keys` | `test: supports selecting multiple roles and submits them all` |

## Escalation guards

| Requirement | Status | Implementation | Verified by |
|-------------|--------|----------------|-------------|
| Cannot assign yourself roles | ✅ | `user_service._assert_not_self` | `test_nobody_can_change_their_own_roles` |
| Cannot grant beyond your own access | ✅ | `role_service._assert_may_grant_levels` | `test_a_role_cannot_grant_more_than_its_creator_holds` |
| Cannot modify protected system roles | ✅ | `PROTECTED_ROLE_KEYS` | `TestProtectedSystemRoles` |
| Cannot bypass the UI via direct API | ✅ | `require_access` | `TestServerSideEnforcement` |
| Client-supplied permissions ignored | ✅ | Never read from the request | `test_the_client_cannot_supply_its_own_permissions` |

## Authentication detail

| Requirement | Status | Implementation | Verified by |
|-------------|--------|----------------|-------------|
| Email + password | ✅ | `schemas/auth.py::LoginRequest` | `TestLogin` |
| Session security | ✅ | JWT access + rotating refresh cookie | `TestSessionLifecycle` |
| Logout | ✅ | `auth_service.logout` | `test_logout_revokes_the_session` |
| Invalid credential handling | ✅ | Identical response for unknown email and wrong password | `test_unknown_email_is_indistinguishable_from_wrong_password` |
| Account status handling | ✅ | `UserStatus.can_authenticate`, re-checked per request | `test_non_active_account_cannot_sign_in`, `test_deactivating_a_user_invalidates_their_live_session` |
| First-login enforcement | ✅ | `get_active_user` blocks all other endpoints | `test_every_other_endpoint_is_blocked` |
| Current + new + confirm on change | ✅ | `ChangePasswordRequest` | `TestChangePassword` |
| Password security requirements | ✅ | `security.validate_password_strength` | `test_security.py::TestPasswordPolicy` |

## User creation detail

| Requirement | Status | Implementation | Verified by |
|-------------|--------|----------------|-------------|
| No public self-registration | ✅ | No unauthenticated create endpoint exists | `test_anonymous_cannot_create` |
| Created by an authorized admin | ✅ | `require_access(ACCESS_MANAGEMENT, CREATE)` | `TestCreateUserAuthorization` |
| Basic fields (name, email, roles, status) | ✅ | `schemas/user.py::UserCreate` | `TestCreateUser` |
| Extensible profile fields | ✅ | `job_title`, `department`, `phone` on `User` | — |
| Secure temporary password | ✅ | `security.generate_temporary_password` | `test_temporary_password_satisfies_the_policy` |
| Marked as requiring change | ✅ | `must_change_password=True` at creation | `test_created_user_must_change_password_on_first_login` |
| Requirement cleared after change | ✅ | `_apply_new_password` | `test_requirement_is_cleared_and_access_granted` |
| No plaintext passwords stored | ✅ | Argon2id only | `test_password_is_hashed_not_stored` |
| No passwords in logs | ✅ | `core/logging.py::RedactionFilter` | `test_security.py::TestLogRedaction` |

## Module access control

| Requirement | Status | Implementation | Verified by |
|-------------|--------|----------------|-------------|
| Access levels Complete / Read Only / Guest | ✅ | `models/enums.py::AccessLevel` (+ `NONE`) | `TestAccessLevelAlgebra` |
| Permissions defined per module | ✅ | `role_module_permissions` table | `TestPermissionResolution` |
| Changeable without restructuring | ✅ | `PUT /roles/{id}/permissions` | `test_permissions_can_be_changed_without_code_changes` |
| Effective permissions determined centrally | ✅ | `services/permission_service.py` — sole decision point | Whole `test_authorization.py` |
| No hard-coded authorization in pages | ✅ | `require_access` server-side; `permissions.ts` client-side | Code review + tests |

## Forgot password

| Requirement | Status | Implementation | Verified by |
|-------------|--------|----------------|-------------|
| Secure, time-limited token | ✅ | `secrets.token_urlsafe(48)`, `PASSWORD_RESET_TTL_MINUTES` | `test_an_expired_token_is_refused` |
| Reset URL generated | ✅ | `services/email/messages.py` | `test_the_link_points_at_the_frontend_reset_route` |
| Email infrastructure prepared | ✅ | `services/email/` | `docs/SMTP.md` |
| Token invalid after use | ✅ | `used_at` | `test_a_token_cannot_be_reused` |
| No account enumeration | ✅ | Always 202 | `test_response_is_identical_for_unknown_addresses` |
| Raw tokens not stored | ✅ | SHA-256 digest only | `test_only_a_hash_of_the_token_is_stored` |

## SMTP / email

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Config structure (host/port/user/pass/secure/from) | ✅ | `SMTPSettings`, `.env.example` |
| Environment variables | ✅ | `SMTP_*` |
| No credentials in source | ✅ | `.env` git-ignored |
| Mocked/logged in development | ✅ | `LogTransport` + dev outbox |
| **Real delivery deliberately not implemented** | ⚠️ | `SMTPTransport.send` raises `NotImplementedError` — as specified |
| Documentation of where to configure | ✅ | `docs/SMTP.md` |
| Relevant URLs documented | ✅ | `docs/ROUTES.md`, `docs/SMTP.md` |

## Dashboard

| Requirement | Status | Implementation | Verified by |
|-------------|--------|----------------|-------------|
| All 12 tools displayed | ✅ | Generated from the permission map | Manual |
| Cards respect authorization | ✅ | `can_view` → locked card | `test_every_module_appears_for_every_user` |
| Easy to add a module | ✅ | Registry entry + seed | `test_superadmin_covers_a_newly_added_module` |
| Registry rather than duplicated logic | ✅ | `app/modules/registry.py` | — |

## Database

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Users, Roles, UserRoles | ✅ | `models/user.py` |
| Modules, Permissions, RolePermissions | ✅ | `models/module.py`, `models/permission.py` |
| PasswordResetTokens | ✅ | `models/token.py` |
| Sessions / refresh tokens | ✅ | `models/token.py::Session` |
| AuditLogs | ✅ | `models/audit.py` |
| M:N User ↔ Roles | ✅ | `user_roles` |
| M:N Role ↔ Module permissions | ✅ | `role_module_permissions` |
| Roles NOT a string column | ✅ | Relational throughout |
| Migrations | ✅ | Alembic `0001_initial` |

## Security

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Secure password hashing | ✅ | Argon2id, configurable, production floors |
| Password validation | ✅ | `validate_password_strength` |
| Secure sessions/tokens | ✅ | Rotation, digests, reuse detection |
| Authentication middleware | ✅ | `api/deps.py::get_current_user` |
| Authorization middleware | ✅ | `api/deps.py::require_access` |
| Input validation | ✅ | Pydantic on every request |
| Protection against auth attacks | ✅ | Lockout, rate limiting, enumeration resistance |
| Secure password reset | ✅ | Hashed, single-use, expiring |
| Token expiration | ✅ | All token types |
| Rate limiting | ✅ | `core/rate_limit.py` |
| Secure cookies | ✅ | HttpOnly, SameSite, Secure, path-scoped |
| CSRF protection | ✅ | Double-submit on cookie endpoints |
| Proper CORS | ✅ | Explicit origin list |
| Environment-based secrets | ✅ | `pydantic-settings` |
| No secrets in git | ✅ | `.gitignore`, `.env.example` |
| No passwords/tokens in logs | ✅ | `RedactionFilter` |
| Database constraints | ✅ | Unique, FK, cascade rules |

## Audit log

| Requirement | Status |
|-------------|--------|
| Login / logout / failed login | ✅ |
| User created / updated | ✅ |
| Role changed | ✅ |
| Password changed | ✅ |
| Password reset requested / completed | ✅ |
| Access/permission changed | ✅ |
| Extensible for future modules | ✅ (`action` is a string, not an enum) |

## Docker

| Requirement | Status |
|-------------|--------|
| Dockerfile(s) | ✅ multi-stage, non-root |
| docker-compose.yml | ✅ 4 services |
| Environment example | ✅ `.env.example` |
| Database service | ✅ |
| Application services | ✅ api + web |
| Volumes | ✅ `db_data` |
| Health checks | ✅ all services |
| Network configuration | ✅ split backend/frontend |
| Startup/migration handling | ✅ `docker-entrypoint.sh` |
| No secrets in compose | ✅ `env_file` only |

## Testing

| Area | Tests |
|------|-------|
| Valid / invalid login, inactive user, logout | ✅ |
| Password change, first-login requirement | ✅ |
| Admin creates user, unauthorized cannot, duplicates, role assignment | ✅ |
| SuperAdmin / Admin / User / Guest authorization | ✅ |
| Module permissions, multiple roles | ✅ |
| Reset request, expiry, invalid token, reuse, success | ✅ |
| Role creation, editing, deletion, protection | ✅ |
| Custom roles, multiple custom roles, effective access | ✅ |
| Dashboard visibility per role and per role combination | ✅ |
| Direct API access without permission | ✅ |
| Create User focus stability and value retention (frontend) | ✅ |
| **Total** | **229 backend + 31 frontend = 260 passing** |

---

## Phase 1 gate

| Criterion | Status |
|-----------|--------|
| Application starts | ✅ |
| Database starts | ✅ |
| Docker Compose works | ✅ |
| Login works using email | ✅ |
| Logout works | ✅ |
| Admin can create users | ✅ |
| Multiple roles work | ✅ |
| SuperAdmin works | ✅ |
| Admin works | ✅ |
| User role exists | ✅ |
| Guest role exists | ✅ |
| Module-level permissions exist | ✅ |
| First-login password change works | ✅ |
| Normal password change works | ✅ |
| Forgot-password flow works | ✅ |
| Password reset token security works | ✅ |
| SMTP configuration structure exists | ✅ |
| SMTP credentials not required locally | ✅ |
| Dashboard displays all tool placeholders | ✅ |
| Dashboard respects permissions | ✅ |
| Authorization enforced server-side | ✅ |
| Tests pass | ✅ 260/260 |
| Documentation exists | ✅ |
| `PRIORITY.md` exists | ✅ |
| `PROJECT_STATUS.md` current | ✅ |
| `CHANGELOG.md` current | ✅ |
| `.env.example` exists | ✅ |
| No secrets committed | ✅ |
| Deployment documentation exists | ✅ |

**Phase 1 gate: PASSED.**
