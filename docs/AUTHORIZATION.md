# Authorization

## Model

Two many-to-many relationships:

```
User  ──M:N──  Role  ──M:N (with access level)──  Module
```

A user holds any number of roles. Each role grants an access level on each
module. **Effective access is the highest level any of the user's roles
grants** — a union, never an intersection.

## Access levels

Three levels are assignable when configuring a role:

| Level | Meaning | Permitted actions |
| ----- | ------- | ----------------- |
| `NONE` | No access. The module is not shown, and the API refuses it. | — |
| `READ_ONLY` | Read-only. | `VIEW` |
| `COMPLETE` | Full access. | `VIEW`, `CREATE`, `UPDATE`, `DELETE`, `MANAGE` |

The mapping from level to permitted actions lives in `app/models/enums.py` and
nowhere else. The API publishes the assignable list at
`GET /api/v1/roles/assignable-access-levels`, so the UI never hard-codes it.

### The deprecated `GUEST` level

A fourth level, `GUEST`, existed originally. It permitted exactly the same
action as `READ_ONLY` (`VIEW`) and only added a rank between `NONE` and
`READ_ONLY`.

Guest access is now expressed the same way as everyone else's — through
effective permissions, with the **Guest role** holding ordinary `READ_ONLY`
grants — rather than through a special level. This keeps role configuration to
the three levels operators actually reason about and removes a hard-coded
special case from the authorization model.

Migration `0002_guest_access` converts existing `GUEST` grants to `READ_ONLY`.
Because both permitted the identical action, no access is widened or narrowed.
The enum value is retained so rows written before the migration still load and
rank correctly, but nothing issues it any more.

## Roles

| Role | Key | Description |
| ---- | --- | ----------- |
| Super Admin | `SUPER_ADMIN` | Unrestricted. Resolution short-circuits to `COMPLETE`. |
| Admin | `ADMIN` | Full access to modules and user administration. |
| User | `USER` | Standard access. **Exact permissions are a placeholder** pending a later phase. |
| Guest | `GUEST` | Read-only visibility of non-sensitive modules. |

Roles are database rows, and administrators can add more at runtime — see
[Role management](#role-management). Only the `is_superuser` flag has special
meaning in code.

### Protected system roles

The four seeded roles are marked `is_system` and are protected:

- they cannot be deleted (`422 role_protected`);
- their machine `key` is immutable;
- Super Admin's permissions cannot be edited at all — its access is computed,
  so a stored row would be misleading (`422 role_immutable`);
- only a Super Admin may modify the Admin role.

Custom roles carry none of these restrictions.

## Default matrix

Seeded on first run; **editable at runtime** through Access Management → Roles.

| Module | Super Admin | Admin | User | Guest |
| ------ | ----------- | ----- | ---- | ----- |
| Dashboard | Complete | Complete | Read only | Read only |
| Team Members | Complete | Complete | Read only | Read only |
| **Access Management** | Complete | Complete | Read only | **None** |
| Asset Inventory | Complete | Complete | Read only | Read only |
| DAS Onboarding | Complete | Complete | Read only | Read only |
| ILO Inventory | Complete | Complete | Read only | Read only |
| Zabbix | Complete | Complete | Read only | Read only |
| Nexus | Complete | Complete | Read only | Read only |
| Cloud Information | Complete | Complete | Read only | Read only |
| Task Updates | Complete | Complete | Read only | Read only |
| Reports | Complete | Complete | Read only | Read only |
| **Settings** | Complete | Complete | **None** | **None** |

Super Admin's column is *computed*, not stored — which is why it automatically
covers modules that do not exist yet.

## Resolution

`app/services/permission_service.py::resolve_permissions` — the single source of
truth:

```
1. any role is_superuser?  → COMPLETE on every active module. Done.
2. otherwise, for each active module:
       levels = grants from all of the user's roles
       effective = max(levels)         # missing row → NONE
3. inactive modules → NONE (excluded from the map)
```

Results are cached in Redis for 60 seconds and invalidated **explicitly**
whenever a user's roles or a role's permissions change, so a permission change
takes effect on the next request rather than after a TTL.

## Enforcing it

Endpoints declare a requirement; they never compute one:

```python
from app.api.deps import require_access
from app.models.enums import ModuleAction

@router.get("", dependencies=[Depends(require_access("TEAM_MEMBERS", ModuleAction.VIEW))])
async def list_team_members(db: DbSession): ...

@router.post("")
async def create_member(
    actor: Annotated[ActiveUser, Depends(require_access("TEAM_MEMBERS", ModuleAction.CREATE))],
): ...
```

Use the second form when the handler needs the acting user; the first when it
does not.

Failure returns `403` with the module, the required action and the caller's
actual level — enough for a support conversation, nothing an attacker gains from.

### Dependency ladder

| Dependency | Guarantees |
| ---------- | ---------- |
| `get_current_user` | Authenticated, active account, live session |
| `get_active_user` | The above **and** no pending password change |
| `require_access(module, action)` | The above **and** the module permission |
| `require_superuser()` | The above **and** a Super Admin role |

Every protected endpoint uses `require_access` or stricter. Only the three
password-change-flow endpoints use `get_current_user` directly.

## Frontend

The API returns the resolved permission map with the session. The client:

- generates sidebar entries from it,
- renders **only** the dashboard cards the user can open — a module resolving to
  `NONE` is not advertised at all (`accessibleModules()`),
- guards routes with `RequireModule`, which renders the Forbidden page for a
  module the user cannot view,
- hides write controls via `can(map, module, 'UPDATE')`.

`accessibleModules()` is the single helper behind both the dashboard grid and
the sidebar, so the two can never disagree about what a user can see.

`src/auth/permissions.ts` mirrors the level→action table. **This is presentation
only.** A user who bypasses the UI still hits server-side enforcement, which is
what the tests assert.

## Escalation guards

| Rule | Why |
| ---- | --- |
| **Nobody may change their own roles** | Self-assignment is the most direct escalation path there is. A second administrator is required. |
| **Nobody may grant a role more access than they hold themselves** | Otherwise anyone with `COMPLETE` on Access Management could mint an all-powerful role and hand it to a confederate. Super Admin is exempt — it already holds everything. |
| Only a Super Admin may grant `SUPER_ADMIN` | Otherwise an admin could promote a confederate to unrestricted access |
| Only a Super Admin may modify a Super Admin account or reset its password | Prevents lateral takeover |
| Nobody may change their own account status | Prevents self-lockout and self-reactivation |
| System roles cannot be deleted | Keeps the platform's own access model intact |
| A role still assigned to users cannot be deleted | Deleting it would silently strip access; reassign first |
| Super Admin permissions are not editable | Its access is computed; a stored row would be misleading |
| Only a Super Admin may edit the `ADMIN` role | An admin cannot widen their own role |

Permissions are **never** taken from the request. No header, cookie or body
field influences what a caller may do — the server resolves access from the
database on every request.

## Role management

Administrators create and configure roles at runtime, with no deployment.

| Capability | Endpoint | Required |
| ---------- | -------- | -------- |
| List roles | `GET /roles` | `ACCESS_MANAGEMENT` VIEW |
| View a role and its matrix | `GET /roles/{id}` | `ACCESS_MANAGEMENT` VIEW |
| Create a role | `POST /roles` | `ACCESS_MANAGEMENT` CREATE |
| Rename / describe a role | `PATCH /roles/{id}` | `ACCESS_MANAGEMENT` UPDATE |
| Configure module permissions | `PUT /roles/{id}/permissions` | `ACCESS_MANAGEMENT` UPDATE |
| Delete a custom role | `DELETE /roles/{id}` | `ACCESS_MANAGEMENT` UPDATE |

A role has a display `name`, an optional `description`, and an immutable machine
`key` derived from the name (`"Asset Manager"` → `ASSET_MANAGER`) unless supplied
explicitly. Keys must match `^[A-Z][A-Z0-9_]{1,63}$` and be unique.

Worked example — an `AssetManager` role:

```json
POST /api/v1/roles
{
  "name": "Asset Manager",
  "description": "Owns the hardware register.",
  "permissions": {
    "DASHBOARD":       "COMPLETE",
    "TEAM_MEMBERS":    "READ_ONLY",
    "ASSET_INVENTORY": "COMPLETE",
    "DAS_ONBOARDING":  "NONE",
    "ZABBIX":          "READ_ONLY",
    "REPORTS":         "READ_ONLY",
    "SETTINGS":        "NONE"
  }
}
```

A holder of that role — and nothing else — sees exactly Dashboard, Team Members,
Asset Inventory, Zabbix and Reports. Every other module is absent from their
dashboard *and* refused by the API.

Modules omitted from `permissions` default to `NONE`, so a new role is closed
until explicitly opened.

## Adding a module

1. Add a `ModuleDefinition` to `app/modules/registry.py` with default grants.
2. Restart the API (the entrypoint re-seeds), or run `python -m app.db.seed`.
3. Protect the new endpoints with `require_access("YOUR_KEY", …)`.

The dashboard card, sidebar entry, guarded route and permission-matrix row all
appear automatically. **No authorization code changes.**
