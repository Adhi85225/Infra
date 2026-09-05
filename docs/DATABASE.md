# Database

PostgreSQL 16. Schema managed exclusively by Alembic — no manual DDL.

## Entity relationships

```
                    ┌───────────────────────┐
                    │        users          │
                    │  id, email (unique)   │
                    │  password_hash        │
                    │  status               │
                    │  must_change_password │
                    └───────────┬───────────┘
                                │
        ┌───────────────────────┼────────────────────────┐
        │                       │                        │
        ▼ 1:N                   ▼ 1:N                    ▼ M:N
┌───────────────┐   ┌────────────────────────┐   ┌──────────────┐
│   sessions    │   │ password_reset_tokens  │   │  user_roles  │
│  token_hash   │   │      token_hash        │   └──────┬───────┘
│ rotated_from  │   └────────────────────────┘          │
└───────────────┘   ┌────────────────────────┐          ▼
                    │   password_history     │   ┌──────────────┐
                    └────────────────────────┘   │    roles     │
                                                 │ key, is_super│
                                                 └──────┬───────┘
                                                        │ M:N
                                                        ▼
                                          ┌──────────────────────────┐
                                          │ role_module_permissions  │
                                          │      access_level        │
                                          └────────────┬─────────────┘
                                                       │
                                                       ▼
                                                ┌──────────────┐
                                                │   modules    │
                                                │ key, route   │
                                                └──────────────┘

┌────────────┐
│ audit_logs │  actor_user_id → users (SET NULL); actor_email denormalised
└────────────┘  so an entry outlives the user it refers to
```

The two many-to-many relationships are the heart of the model:
**User ↔ Role** and **Role ↔ Module** (carrying an access level).

## Tables

### `users`

| Column | Type | Notes |
| ------ | ---- | ----- |
| `id` | uuid PK | |
| `email` | varchar(320) **unique**, indexed | always stored lower-cased, so uniqueness is effectively case-insensitive |
| `first_name`, `last_name` | varchar(120) | |
| `password_hash` | text, nullable | Argon2id encoded hash; nullable so an account can exist before a credential is set |
| `status` | varchar(32), indexed | `ACTIVE` / `INACTIVE` / `SUSPENDED` |
| `must_change_password` | boolean | blocks every endpoint except the change flow |
| `job_title`, `department`, `phone` | nullable | extensible profile fields; adding more does not affect auth |
| `last_login_at`, `password_changed_at` | timestamptz | |
| `failed_login_count` | integer | reset on success |
| `locked_until` | timestamptz | lockout expiry |
| `created_by_id` | uuid FK → users (SET NULL) | who created the account |
| `created_at`, `updated_at` | timestamptz | |

### `roles`

| Column | Type | Notes |
| ------ | ---- | ----- |
| `id` | uuid PK | |
| `key` | varchar(64) **unique** | stable machine key (`SUPER_ADMIN`, `ADMIN`, …) |
| `name`, `description` | | |
| `is_system` | boolean | seeded roles (`SUPER_ADMIN`, `ADMIN`, `USER`, `GUEST`); protected from deletion and re-keying. Custom roles created through the API are always `false` |
| `is_superuser` | boolean | **short-circuits permission resolution to COMPLETE** |
| `sort_order` | integer | display order |

### `user_roles`

Association table. Unique on `(user_id, role_id)`; both FKs cascade on delete.
Also records `assigned_at` and `assigned_by_id` for the audit trail.

There is exactly one role table and one association table. Custom roles created
by administrators are ordinary `roles` rows — no separate model, no duplication.

### `modules`

| Column | Type | Notes |
| ------ | ---- | ----- |
| `key` | varchar(64) **unique** | referenced by permission checks |
| `name`, `description`, `icon` | | |
| `route` | varchar(160) | the frontend path this module owns |
| `sort_order` | integer | |
| `is_active` | boolean | inactive modules resolve to `NONE` everywhere |
| `is_core` | boolean | platform modules (Dashboard, Access Management, Settings) |
| `is_implemented` | boolean | false while a tool is a placeholder |

### `role_module_permissions`

| Column | Type | Notes |
| ------ | ---- | ----- |
| `role_id` | uuid FK → roles (CASCADE), indexed | |
| `module_id` | uuid FK → modules (CASCADE), indexed | |
| `access_level` | varchar(32) | `NONE` / `READ_ONLY` / `COMPLETE` (plus the deprecated `GUEST`) |

Unique on `(role_id, module_id)`. **A missing row means `NONE`** — absence is the
default, so a new module is closed until explicitly granted.

`SUPER_ADMIN` deliberately has *no rows here*: its access is computed, which is
what lets it cover modules added in the future.

Migration `0002_guest_access` converted every `GUEST` row to `READ_ONLY`. The
two permitted identical actions, so nothing was widened or narrowed; guest
access is now an ordinary read-only grant rather than a special level.

### `sessions`

One refresh-token lifetime — effectively one signed-in device.

| Column | Notes |
| ------ | ----- |
| `token_hash` | varchar(64) **unique**, indexed — SHA-256 of the token; the token itself is never stored |
| `expires_at` | rotation does **not** extend this |
| `revoked_at`, `revoked_reason` | `rotated`, `logout`, `reuse_detected`, `password_changed`, … |
| `rotated_from_id` | self-FK forming the rotation chain, so a whole family can be revoked |
| `ip_address` (inet), `user_agent` | |

### `password_reset_tokens`

`token_hash` (unique, indexed), `expires_at`, `used_at`, `requested_ip`.
A token is usable only while `used_at IS NULL AND expires_at > now()`.

### `password_history`

Previous Argon2id hashes per user, so a recent password cannot be reused.
Trimmed to `PASSWORD_HISTORY_DEPTH` entries.

### `audit_logs`

| Column | Notes |
| ------ | ----- |
| `actor_user_id` | FK → users (SET NULL) |
| `actor_email` | denormalised, so the entry stays meaningful after user deletion |
| `action` | plain string, **not** an enum — new modules can log new actions without a migration |
| `success` | boolean |
| `entity_type`, `entity_id` | what was acted on |
| `ip_address` (inet), `user_agent` | |
| `context` | JSONB, redacted before it is written |
| `created_at` | indexed |

Append-only by convention: nothing in the application updates or deletes rows.

## Design decisions

**UUID primary keys.** Ids appear in URLs and audit entries; sequential integers
would leak volume and make records guessable.

**Timezone-aware timestamps everywhere.** `timestamptz` avoids an entire class
of expiry bugs.

**Enums stored as strings, not PostgreSQL enum types.** Adding a value to a
PostgreSQL enum requires a migration and locks; a `varchar` with validation in
the application layer keeps the audit log and access levels extensible.

**Naming convention configured on the metadata.** Alembic emits stable,
predictable constraint names, so autogenerated migrations stay reviewable.

## Migrations

### Applied migrations

| Revision | Purpose |
| -------- | ------- |
| `0001_initial` | Full Phase 1 schema |
| `0002_guest_access` | Data migration retiring the `GUEST` access level in favour of `READ_ONLY`. Non-destructive; downgrade is a deliberate no-op because which rows were originally `GUEST` is not recorded. |

```bash
cd backend
./.venv/bin/alembic upgrade head           # apply
./.venv/bin/alembic revision --autogenerate -m "description"   # create
./.venv/bin/alembic downgrade -1           # roll back one
./.venv/bin/alembic current                # where am I
```

In Docker, `docker-entrypoint.sh` runs `alembic upgrade head` before the server
starts, so a deployment migrates itself.

**Always review an autogenerated migration.** Alembic detects added and removed
columns well; it cannot infer a rename, and will emit a drop plus an add — which
loses data.

## Seeding

`python -m app.db.seed` is idempotent and runs on every container start:

1. Create or refresh role metadata from the registry.
2. Create or refresh module rows from the registry.
3. Apply default grants **only where no row exists** — an administrator's
   customisations are never overwritten.
4. Create the bootstrap Super Admin, but only when the database has no users at
   all.
