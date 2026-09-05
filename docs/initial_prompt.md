# Multipurpose Helper Tools — Application Build Instructions

You are the **lead software architect, senior full-stack developer, DevOps engineer, and technical documentation owner** for this project.

We are going to build a **multipurpose internal helper-tools web application** phase-by-phase.

Your job is to build the application, maintain its architecture, documentation, priorities, progress tracking, deployment configuration, and development standards throughout the project.

---

# 1. APPLICATION OVERVIEW

The application will eventually contain multiple internal tools/modules:

* 🏠 Dashboard
* 👥 Team Members
* 🔐 Access Management
* 💻 Asset Inventory
* 👤 DAS Onboarding
* 📦 ILO Inventory
* 📊 Zabbix
* 🛡️ Nexus
* ☁️ Cloud Information
* ✅ Task Updates
* 📈 Reports

  * Manager Reports
  * Admin Reports
* ⚙️ Settings

  * Admin only
* More tools/modules will be added later.

The application must therefore be designed as a **modular, scalable platform**, not as a single-purpose application.

Do NOT tightly couple the authentication system to future tools.

---

# 2. DEVELOPMENT APPROACH

We will develop this application **phase-by-phase**.

## Phase 1 — Authentication & Access Foundation

For the first phase, implement ONLY the authentication and authorization foundation plus the dashboard UI placeholders.

Do not prematurely implement the actual functionality of the future tools.

Phase 1 must include:

1. Login
2. User creation
3. User roles
4. Multiple roles per user
5. Module/tool-level access control
6. First-login password change
7. Forgot password
8. Change password
9. Email-based login
10. SMTP configuration structure
11. Dashboard with tool placeholders
12. Docker deployment
13. Docker Compose
14. Complete project documentation
15. Development/progress tracking

---

# 3. USER AUTHENTICATION

Users must log in using their **email address**.

Authentication must include:

### Login

* Email
* Password
* Remember appropriate authentication/session security
* Logout
* Invalid credential handling
* Account status handling
* First-login password-change enforcement

### Password Change

Authenticated users must be able to change their password.

Require:

* Current password
* New password
* Confirm new password

Apply appropriate password security requirements.

---

# 4. USER CREATION / REGISTRATION

There must NOT be public self-registration.

Users are created by an authorized **Admin**.

Admin should be able to create a user with basic details such as:

* First name
* Last name
* Email
* Role(s)
* Account status
* Other appropriate basic fields

The exact profile fields can be kept extensible.

When an Admin creates a new user:

1. User account is created.
2. A temporary/initial password mechanism is established securely.
3. User is marked as requiring password change.
4. On first successful login, the user MUST be forced to change their password.
5. After changing the password successfully, the first-login requirement is removed.

Do not expose passwords in logs.

Do not store plaintext passwords.

Use secure password hashing.

---

# 5. ROLES

The system must support **multiple roles per user**.

Initial roles:

### SuperAdmin

Complete access to the entire application.

### Admin

Complete access to the application.

### User

Limited access.

The exact permissions for User will be defined in a later phase.

### Guest

Read-only access.

The authorization system must be designed so additional roles can easily be added later.

Do NOT hard-code authorization logic throughout individual pages/components.

Use a centralized permission/authorization architecture.

---

# 6. TOOL/MODULE ACCESS CONTROL

Every application tool/module must support access levels.

Initial access levels:

* Complete
* Read Only
* Guest

The architecture should allow permissions to be defined at the module/tool level.

For example:

| Module            | Complete | Read Only  | Guest |
| ----------------- | -------- | ---------- | ----- |
| Dashboard         | Yes      | Yes        | Yes   |
| Team Members      | Yes      | Yes        | Yes   |
| Access Management | Yes      | No/limited | No    |
| Asset Inventory   | Yes      | Yes        | Yes   |
| DAS Onboarding    | Yes      | Yes        | Yes   |
| ILO Inventory     | Yes      | Yes        | Yes   |
| Zabbix            | Yes      | Yes        | Yes   |
| Nexus             | Yes      | Yes        | Yes   |
| Cloud Information | Yes      | Yes        | Yes   |
| Task Updates      | Yes      | Yes        | Yes   |
| Reports           | Yes      | Yes        | Yes   |
| Settings          | Yes      | No         | No    |

IMPORTANT:

The above permissions are only an initial example.

Design the system so permissions can be changed later without major code restructuring.

A user may have multiple roles.

The effective permissions should be determined centrally.

---

# 7. ACCESS MANAGEMENT

Create the foundation for an **Access Management** section.

It should eventually allow authorized administrators to manage:

* Users
* Roles
* Permissions
* Module access
* Account status

For Phase 1, implement the required functionality necessary for user and role management.

Do not overbuild advanced access-management features unless required for the Phase 1 authentication architecture.

---

# 8. FORGOT PASSWORD

Implement a secure forgot-password workflow.

Expected flow:

1. User selects "Forgot Password".
2. User enters email.
3. System generates a secure, time-limited password reset token.
4. Reset URL is generated.
5. Email delivery infrastructure should be prepared.
6. User opens reset URL.
7. User sets a new password.
8. Token becomes invalid after use/expiration.

Do not reveal whether an email address exists in a way that enables easy account enumeration.

Password reset tokens must be securely generated and stored.

Do not store raw reset tokens if avoidable.

---

# 9. SMTP / EMAIL SYSTEM

Create the application's email infrastructure/configuration.

However:

## DO NOT IMPLEMENT REAL SMTP DELIVERY YET.

Create the configuration structure/placeholders for:

* SMTP host
* SMTP port
* SMTP username
* SMTP password
* SMTP encryption/security
* From email
* From name

Use environment variables.

Example:

```env
SMTP_HOST=
SMTP_PORT=
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_SECURE=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=
```

Do NOT put real SMTP credentials into source code.

Do NOT commit secrets.

For now, email sending can be mocked/logged during development.

---

# 10. IMPORTANT — SMTP URL LOGGING

Since SMTP will be configured manually later:

Create clear application/deployment documentation explaining exactly where SMTP configuration must be added.

Also provide the relevant URLs/endpoints/routes in the project documentation/log, such as:

* Forgot Password page
* Password Reset page
* Login page
* Change Password page

The actual SMTP service configuration will be added manually later.

Do not block development because SMTP credentials are not currently available.

---

# 11. DASHBOARD / HOMEPAGE

Create the main application Dashboard.

The dashboard should show the available tools/modules as clean UI cards/placeholders.

Display:

🏠 Dashboard
👥 Team Members
🔐 Access Management
💻 Asset Inventory
👤 DAS Onboarding
📦 ILO Inventory
📊 Zabbix
🛡️ Nexus
☁️ Cloud Information
✅ Task Updates
📈 Reports
⚙️ Settings

These are currently **placeholders**.

Do NOT implement their actual functionality in Phase 1.

Cards should respect authorization.

For example:

* If user has access → show/enable module.
* If user does not have access → hide or disable according to the centralized access-control strategy.

The Dashboard must be designed so adding a new module later is easy.

Prefer a module registry/configuration approach rather than manually duplicating authorization logic for every card.

---

# 12. APPLICATION ARCHITECTURE

Before writing significant code:

1. Inspect the repository.
2. Determine whether an existing project structure exists.
3. If starting from an empty repository, choose an appropriate modern production-ready stack.
4. Explain the architecture briefly.
5. Create the initial project structure.
6. Keep frontend/backend/database responsibilities cleanly separated where appropriate.

The architecture must support:

* Authentication
* Authorization
* Multiple roles
* Module permissions
* Future modules
* Auditing
* Configuration
* API expansion
* Database migrations
* Docker deployment

Use established security practices.

Avoid unnecessary complexity.

---

# 13. DATABASE DESIGN

Design a proper relational database schema.

At minimum, consider entities such as:

* Users
* Roles
* UserRoles
* Modules/Tools
* Permissions/AccessLevels
* RolePermissions
* PasswordResetTokens
* Sessions/RefreshTokens if applicable
* AuditLogs

The exact schema is your responsibility.

The design must support:

### Many-to-many:

User ↔ Roles

and:

Role ↔ Module Permissions

Do not implement roles as a single string field in the User table.

Use proper relational modeling.

---

# 14. SECURITY REQUIREMENTS

Treat security as a first-class requirement.

Implement:

* Secure password hashing
* Password validation
* Secure sessions/tokens
* Authentication middleware
* Authorization middleware
* Input validation
* Protection against common authentication attacks
* Secure password reset
* Token expiration
* Rate limiting where appropriate
* Secure cookies where applicable
* CSRF protection where applicable
* Proper CORS configuration
* Environment-based secrets
* No secrets committed to Git
* No passwords/tokens in logs
* Appropriate database constraints

Do not invent insecure shortcuts merely to make Phase 1 faster.

---

# 15. AUDIT LOG FOUNDATION

Create an audit-log foundation.

At minimum, important security/admin actions should be capable of being recorded, such as:

* Login
* Logout
* Failed login
* User created
* User updated
* Role changed
* Password changed
* Password reset requested
* Password reset completed
* Access/permission changed

The audit system should be extensible for future modules.

---

# 16. DOCKER

Create a production-oriented Docker setup.

Include:

* Dockerfile(s)
* docker-compose.yml
* Environment configuration example
* Database service
* Application service(s)
* Appropriate volumes
* Health checks where appropriate
* Network configuration
* Startup/migration handling

The application should be deployable using Docker Compose.

The project must include clear instructions such as:

```bash
docker compose up -d
```

and the required migration/setup commands.

Do not put secrets directly inside docker-compose.yml.

Provide:

```text
.env.example
```

---

# 17. DOCUMENTATION REQUIREMENTS

Documentation is a core requirement of this project.

Create and maintain a `/docs` directory.

At minimum create:

```text
docs/
├── README.md
├── ARCHITECTURE.md
├── REQUIREMENTS.md
├── DATABASE.md
├── AUTHENTICATION.md
├── AUTHORIZATION.md
├── API.md
├── DEPLOYMENT.md
├── ENVIRONMENT.md
├── SECURITY.md
├── ROADMAP.md
├── CHANGELOG.md
└── DEVELOPMENT.md
```

Adjust the structure if your chosen architecture requires additional documents.

Documentation must be updated whenever the implementation changes something important.

---

# 18. PRIORITY FILE

Create:

```text
PRIORITY.md
```

This is one of the most important files in the repository.

It must contain the application's prioritized development roadmap.

Example structure:

```text
# Application Development Priorities

## P0 — Foundation
- Project setup
- Database
- Authentication
- Authorization
- Roles
- User management
- Password reset
- Password change
- Dashboard
- Docker
- Documentation

## P1 — Core Administration
- Team Members
- Access Management
- Audit Logs
- Admin Settings

## P2 — Infrastructure Tools
- Asset Inventory
- DAS Onboarding
- ILO Inventory
- Zabbix
- Nexus
- Cloud Information

## P3 — Operations
- Task Updates
- Reports

## P4 — Future
- Additional tools
- Integrations
- Automation
```

This is only a starting structure.

Maintain and update it as the project evolves.

Do not mark work complete unless it is actually implemented and verified.

---

# 19. PROJECT STATUS / WHAT'S GOING ON FILE

Create:

```text
PROJECT_STATUS.md
```

This file must always show the current state of development.

Use a structure such as:

```markdown
# Project Status

## Current Phase
Phase 1 — Authentication & Access Foundation

## Overall Status
In Progress

## Current Work
- ...

## Completed
- ...

## In Progress
- ...

## Blocked
- ...

## Next Steps
- ...

## Known Issues
- ...

## Decisions Made
- ...

## Last Updated
YYYY-MM-DD
```

Update this file throughout development.

Someone opening the repository should be able to understand **what is happening right now** without reading the entire codebase.

---

# 20. CHANGELOG

Maintain:

```text
CHANGELOG.md
```

Record meaningful implementation changes.

Use a structure such as:

```markdown
# Changelog

## [Unreleased]

### Added
### Changed
### Fixed
### Security
### Documentation
```

---

# 21. REQUIREMENTS TRACEABILITY

Maintain a requirements checklist.

Every Phase 1 requirement should be traceable to implementation.

For example:

| Requirement                 | Status | Location |
| --------------------------- | ------ | -------- |
| Email login                 | ⬜      |          |
| User creation               | ⬜      |          |
| Multiple roles              | ⬜      |          |
| SuperAdmin                  | ⬜      |          |
| Admin                       | ⬜      |          |
| User                        | ⬜      |          |
| Guest                       | ⬜      |          |
| Module access               | ⬜      |          |
| First login password change | ⬜      |          |
| Forgot password             | ⬜      |          |
| Change password             | ⬜      |          |
| SMTP configuration          | ⬜      |          |
| Dashboard placeholders      | ⬜      |          |
| Docker                      | ⬜      |          |
| Docker Compose              | ⬜      |          |
| Documentation               | ⬜      |          |

You may place this in `REQUIREMENTS.md`.

---

# 22. TESTING

Phase 1 must include testing.

At minimum create tests for:

### Authentication

* Valid login
* Invalid login
* Inactive user
* Logout
* Password change
* First-login password requirement

### User Management

* Admin creates user
* Unauthorized user cannot create user
* Duplicate email handling
* Role assignment

### Authorization

Test:

* SuperAdmin
* Admin
* User
* Guest

Test module permissions.

Test multiple roles.

### Password Reset

* Reset request
* Token expiration
* Invalid token
* Token reuse
* Successful password reset

Tests should be automated where practical.

---

# 23. UI/UX

Build a clean, professional internal enterprise-style interface.

Requirements:

* Responsive design
* Desktop-first but mobile-friendly
* Consistent navigation
* Sidebar navigation where appropriate
* Clear role/access indicators
* Loading states
* Empty states
* Error states
* Form validation
* Success/error notifications
* Accessible controls

Do not make the UI overly flashy.

Prioritize usability.

---

# 24. ROUTING

Create clean routes.

At minimum, establish routes conceptually similar to:

```text
/login
/forgot-password
/reset-password
/change-password
/dashboard
/users
/access-management
/settings
```

Future module routes should follow a consistent structure.

The exact routing implementation depends on the chosen framework.

---

# 25. DEVELOPMENT RULES

Follow these rules throughout the project:

### Rule 1

Do not implement future modules prematurely.

### Rule 2

Build reusable foundations.

### Rule 3

Do not duplicate authorization logic.

### Rule 4

Do not hard-code permissions throughout UI components.

### Rule 5

Keep secrets out of source control.

### Rule 6

Use migrations for database changes.

### Rule 7

Update documentation when architecture changes.

### Rule 8

Update `PROJECT_STATUS.md` after meaningful work.

### Rule 9

Update `PRIORITY.md` when priorities change.

### Rule 10

Update `CHANGELOG.md` for meaningful changes.

### Rule 11

Write tests for security-sensitive functionality.

### Rule 12

Do not claim something is implemented unless it has actually been implemented and verified.

---

# 26. PHASE GATE

Phase 1 is complete only when all of the following are working:

* [ ] Application starts successfully
* [ ] Database starts successfully
* [ ] Docker Compose works
* [ ] Login works using email
* [ ] Logout works
* [ ] Admin can create users
* [ ] Multiple roles work
* [ ] SuperAdmin works
* [ ] Admin works
* [ ] User role exists
* [ ] Guest role exists
* [ ] Module-level permissions exist
* [ ] First-login password change works
* [ ] Normal password change works
* [ ] Forgot-password flow works
* [ ] Password reset token security works
* [ ] SMTP configuration structure exists
* [ ] SMTP credentials are NOT required for local development
* [ ] Dashboard displays all tool placeholders
* [ ] Dashboard respects permissions
* [ ] Authorization is enforced server-side
* [ ] Tests pass
* [ ] Documentation exists
* [ ] `PRIORITY.md` exists
* [ ] `PROJECT_STATUS.md` is current
* [ ] `CHANGELOG.md` is current
* [ ] `.env.example` exists
* [ ] No secrets are committed
* [ ] Deployment documentation exists

---

# 27. IMPORTANT — DO NOT ASK FOR EVERYTHING AT ONCE

Work incrementally.

First inspect the existing repository.

Then determine:

1. Existing files/project
2. Existing technology
3. Existing dependencies
4. Existing database
5. Existing configuration

If the repository is empty, select an appropriate production-ready stack.

Before major implementation, provide a concise implementation plan.

Then begin Phase 1.

Do not wait for approval after every tiny step.

Make sensible engineering decisions yourself.

Only stop and ask me when a decision genuinely requires my input or would materially change the architecture.

---

# 28. DEFINITION OF DONE

A feature is considered complete only when:

1. Code is implemented.
2. Database changes are implemented if required.
3. API/backend logic works.
4. UI works.
5. Authorization is enforced.
6. Error handling exists.
7. Tests are added.
8. Tests pass.
9. Documentation is updated.
10. Project status is updated.

---

# 29. FUTURE-PROOFING

The following modules will be developed later:

```text
Dashboard
Team Members
Access Management
Asset Inventory
DAS Onboarding
ILO Inventory
Zabbix
Nexus
Cloud Information
Task Updates
Reports
Settings
```

Design the system so each future module can be developed independently.

Prefer a structure similar to:

```text
Core
 ├── Authentication
 ├── Authorization
 ├── Users
 ├── Roles
 ├── Permissions
 ├── Audit
 └── Configuration

Modules
 ├── Dashboard
 ├── Team Members
 ├── Asset Inventory
 ├── DAS Onboarding
 ├── ILO Inventory
 ├── Zabbix
 ├── Nexus
 ├── Cloud Information
 ├── Task Updates
 └── Reports
```

The exact directory structure is up to you based on the chosen framework.

---

# 30. FIRST TASK

Start by inspecting the repository.

Then:

### Step 1

Determine the existing project state.

### Step 2

Recommend or select the technology stack if one does not already exist.

### Step 3

Create the architecture.

### Step 4

Create the initial documentation structure.

### Step 5

Create:

```text
PRIORITY.md
PROJECT_STATUS.md
CHANGELOG.md
```

### Step 6

Implement Phase 1.

### Step 7

Create Docker and Docker Compose deployment.

### Step 8

Run tests and verify the application.

### Step 9

Update all documentation and status files.

### Step 10

At the end, provide a concise report containing:

* What was implemented
* Files/directories created
* Database schema
* Authentication flow
* Authorization model
* How to run locally
* How to run with Docker
* Required environment variables
* URLs/routes
* Tests performed
* Known limitations
* What should be built next

Remember:

**This is a long-term application. Build the foundation carefully rather than rushing Phase 1.**
