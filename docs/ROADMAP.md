# Roadmap

Phase-level plan. The prioritised, actionable list is [PRIORITY.md](../PRIORITY.md).

## Phase 1 — Authentication & Access Foundation ✅ COMPLETE

Delivered: email sign-in, sessions with rotation and theft detection, multiple
roles per user, database-driven module permissions, admin user management,
first-login and voluntary password change, forgot/reset password, the audit
foundation, the dashboard with placeholders, Docker deployment, 158 tests and
full documentation.

Deliberately excluded: real SMTP delivery, and the functionality of any
individual tool.

## Phase 2 — Core Administration

Make the platform usable day to day without manual credential handling.

- **Real SMTP delivery** — the single highest-value remaining item.
- **Team Members** — the first real tool, and the template for the rest.
- **Admin Settings** — editable configuration instead of environment-only.
- Audit log filtering and CSV export.
- User self-service profile editing.
- Bulk user import.

Exit criteria: an administrator can onboard a user end to end without touching
a log file or a shell.

## Phase 3 — Infrastructure Tools

Each is independent and builds on the Phase 1 core:

Asset Inventory · DAS Onboarding · ILO Inventory · Zabbix · Nexus ·
Cloud Information.

Expect these to introduce the first **external integrations**. Anticipated work:
a shared integration layer (credential storage, retry/backoff, caching) and
background jobs — Redis is already in the stack.

## Phase 4 — Operations

- Task Updates.
- Reports — Manager and Admin views.

Reporting will likely need read models or scheduled aggregation rather than
querying operational tables directly.

## Phase 5 — Platform Maturity

- **SSO / OIDC** — the auth layer is decoupled specifically to allow this.
- **Two-factor authentication** — the session model already accommodates a step.
- Per-user permission overrides.
- Notifications (depends on SMTP).
- Metrics and tracing.
- API tokens for machine access.

## Design commitments

These hold across every phase:

1. **One authorization path.** Every new module uses `require_access`.
2. **Modules stay independent.** No tool imports another tool's internals.
3. **The database stays authoritative for permissions.** Rules change without a
   deployment.
4. **Security is not deferred.** New endpoints ship with tests.
5. **Documentation ships with the code**, not after it.
