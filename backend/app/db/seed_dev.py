"""Development-only seed: test accounts and sample task data.

    python -m app.db.seed_dev

**Not** part of container startup. ``docker-entrypoint.sh`` runs
``app.db.seed`` (roles, modules, permissions, bootstrap admin) and nothing here,
so a deployment never grows demonstration data by accident. Running this against
``ENVIRONMENT=production`` is refused outright.

Passwords are generated with the same helper the user-administration flow uses
and printed once, exactly as the bootstrap admin's is. Nothing is hardcoded, so
there is no plaintext credential in source control.

Re-running is safe: the accounts are reused, their passwords reset to freshly
generated ones, and the sample tasks replaced rather than duplicated.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionFactory, dispose_engine
from app.core.logging import configure_logging
from app.core.security import generate_temporary_password, hash_password
from app.models.enums import TaskService, TaskStatus, UserStatus
from app.models.task import Task
from app.models.user import Role, User, UserRole
from app.modules.registry import ROLE_ADMIN, ROLE_USER

#: Marks every row this script creates, so it can be recognised and replaced.
DEV_MARKER = "[dev-seed]"

#: Test accounts. The domain matches the addresses the project already seeds.
DEV_USERS: tuple[tuple[str, str, str, str], ...] = (
    ("admin.tasktest@example.internal", "Task", "Admin", ROLE_ADMIN),
    ("task.user1@example.internal", "Task", "UserOne", ROLE_USER),
    ("task.user2@example.internal", "Task", "UserTwo", ROLE_USER),
)

#: Sample tasks: (days ago, service, status, reference, site, description, remarks, user index)
#:
#: Spread across every service, every status, all three users and a fortnight of
#: dates, so the dashboard's charts, filters and trend all have something real
#: to show.
# A data table reads best aligned two lines to a row; the formatter would give
# each field a line of its own and turn 22 rows into 176.
# fmt: off
DEV_TASKS: tuple[tuple[int, TaskService, TaskStatus, str, str, str, str | None, int], ...] = (
    # days ago, service, status, reference, site,
    #   description, remarks, index into DEV_USERS
    (0, TaskService.DAS, TaskStatus.INPROGRESS, "INC-4471", "Chennai DC",
     "Replaced failed disk in shelf 3", "Awaiting vendor RMA", 1),
    (0, TaskService.ZABBIX, TaskStatus.TRIAGE, "INC-4472", "Bangalore DC",
     "Investigating repeated CPU alerts on app-07", None, 2),
    (0, TaskService.SERVERS, TaskStatus.CREATED, "WO-2210", "Chennai DC",
     "Applied September security patches to the web tier", None, 1),
    (0, TaskService.ACCESS_MANAGEMENT, TaskStatus.COMPLETED, "JIRA-881", "HQ",
     "Onboarded three contractors", "Access reviewed", 0),
    (1, TaskService.ILO, TaskStatus.ONHOLD, "INC-4460", "Hyderabad DC",
     "iLO firmware upgrade batch 2", "Blocked on change window", 2),
    (1, TaskService.NEXUS, TaskStatus.COMPLETED, "JIRA-874", "HQ",
     "Cleaned up stale release repositories", "Freed 240GB", 1),
    (1, TaskService.DAS, TaskStatus.COMPLETED, "INC-4455", "Chennai DC",
     "Expanded storage pool for analytics", None, 0),
    (2, TaskService.ZABBIX, TaskStatus.COMPLETED, "INC-4441", "Bangalore DC",
     "Added host group for the payments tier", None, 1),
    (2, TaskService.SERVERS, TaskStatus.INPROGRESS, "WO-2198", "Mumbai DC",
     "Kernel patch rollout to the database tier", "Two of five done", 2),
    (3, TaskService.ACCESS_MANAGEMENT, TaskStatus.INPROGRESS, "JIRA-869", "HQ",
     "Quarterly access review for the platform team", None, 0),
    (3, TaskService.ILO, TaskStatus.CREATED, "INC-4430", "Hyderabad DC",
     "Audit iLO credentials across the estate", None, 2),
    (4, TaskService.NEXUS, TaskStatus.TRIAGE, "INC-4422", "HQ",
     "Intermittent 502 from the proxy repository", "Reproduced twice", 1),
    (5, TaskService.DAS, TaskStatus.ONHOLD, "WO-2180", "Chennai DC",
     "Controller cache battery replacement", "Part on order", 2),
    (5, TaskService.SERVERS, TaskStatus.COMPLETED, "WO-2179", "Mumbai DC",
     "BIOS and firmware update across the app tier", None, 0),
    (6, TaskService.ZABBIX, TaskStatus.COMPLETED, "INC-4401", "Bangalore DC",
     "Tuned noisy disk-latency triggers", "False positives down", 1),
    (7, TaskService.ACCESS_MANAGEMENT, TaskStatus.COMPLETED, "JIRA-850", "HQ",
     "Offboarded departing staff", None, 0),
    (8, TaskService.ILO, TaskStatus.COMPLETED, "INC-4388", "Hyderabad DC",
     "Replaced faulty management NIC", None, 2),
    (9, TaskService.NEXUS, TaskStatus.COMPLETED, "JIRA-841", "HQ",
     "Migrated build artefacts to the new layout", None, 1),
    (10, TaskService.DAS, TaskStatus.TRIAGE, "INC-4370", "Chennai DC",
     "Unexplained latency spike on the array", "Vendor engaged", 2),
    (11, TaskService.SERVERS, TaskStatus.CREATED, "WO-2150", "Mumbai DC",
     "Patch compliance report for the quarter", None, 0),
    (12, TaskService.ZABBIX, TaskStatus.ONHOLD, "INC-4355", "Bangalore DC",
     "Proxy migration to the new subnet", "Waiting on network", 1),
    (13, TaskService.ILO, TaskStatus.INPROGRESS, "INC-4340", "Hyderabad DC",
     "Standardise iLO alert destinations", None, 2),
)
# fmt: on


async def seed_users(db: AsyncSession) -> list[tuple[User, str, str]]:
    """Create or refresh the test accounts.

    Returns each account with its generated password and role name. The role
    is carried explicitly rather than read back off ``user.roles``, which
    would lazy-load a relationship on a freshly flushed object.
    """
    created: list[tuple[User, str, str]] = []

    for email, first_name, last_name, role_key in DEV_USERS:
        password = generate_temporary_password()
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()

        if user is None:
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                password_hash=hash_password(password),
                status=UserStatus.ACTIVE,
                # False on purpose: a tester who is forced through the
                # change-password screen cannot reach the feature under test.
                must_change_password=False,
                job_title=f"{DEV_MARKER} test account",
            )
            db.add(user)
            await db.flush()
        else:
            user.password_hash = hash_password(password)
            user.status = UserStatus.ACTIVE
            user.must_change_password = False
            user.job_title = f"{DEV_MARKER} test account"

        role = (await db.execute(select(Role).where(Role.key == role_key))).scalar_one()
        held = (
            await db.execute(
                select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
            )
        ).scalar_one_or_none()
        if held is None:
            db.add(UserRole(user_id=user.id, role_id=role.id))

        created.append((user, password, role.name))

    await db.flush()
    return created


async def seed_tasks(db: AsyncSession, users: list[User]) -> int:
    """Replace the sample tasks, leaving anything a human entered untouched."""
    # Only rows this script wrote carry the marker in their description, so a
    # task someone entered by hand is never swept away by a re-run.
    await db.execute(delete(Task).where(Task.description.like(f"{DEV_MARKER}%")))

    today = date.today()
    for days_ago, service, status, reference, site, description, remarks, owner in DEV_TASKS:
        db.add(
            Task(
                task_date=today - timedelta(days=days_ago),
                reference_number=reference,
                site_name=site,
                # Marked so a re-run replaces exactly these rows.
                description=f"{DEV_MARKER} {description}",
                remarks=remarks,
                status=status,
                service=service,
                user_id=users[owner].id,
                created_by_id=users[owner].id,
            )
        )
    await db.flush()
    return len(DEV_TASKS)


async def main() -> None:
    configure_logging()

    if settings.is_production:
        print(
            "Refusing to seed development data: ENVIRONMENT is 'production'.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    async with SessionFactory() as db:
        accounts = await seed_users(db)
        count = await seed_tasks(db, [user for user, _, _ in accounts])
        await db.commit()

        print("=" * 72, file=sys.stderr)
        print("DEVELOPMENT TEST ACCOUNTS -- not for production use", file=sys.stderr)
        print("=" * 72, file=sys.stderr)
        for user, password, role_name in accounts:
            print(f"  {user.email}", file=sys.stderr)
            print(f"    password: {password}", file=sys.stderr)
            print(f"    role:     {role_name}", file=sys.stderr)
        print(
            f"\n  Seeded {count} sample tasks across "
            f"{len(TaskService)} services and {len(TaskStatus)} statuses.",
            file=sys.stderr,
        )
        print("=" * 72, file=sys.stderr)

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
