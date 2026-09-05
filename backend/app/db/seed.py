"""Idempotent database seeding.

Synchronises the role and module catalogue from :mod:`app.modules.registry` and
ensures a bootstrap Super Admin exists.  Safe to run on every deployment: it
only creates what is missing and never overwrites an administrator's later
permission edits.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionFactory, dispose_engine
from app.core.logging import configure_logging, get_logger
from app.core.security import generate_temporary_password, hash_password
from app.models.enums import AccessLevel, UserStatus
from app.models.module import Module
from app.models.permission import RoleModulePermission
from app.models.user import Role, User, UserRole
from app.modules.registry import (
    MODULE_DEFINITIONS,
    ROLE_DEFINITIONS,
    ROLE_SUPER_ADMIN,
)

logger = get_logger(__name__)


async def sync_roles(db: AsyncSession) -> dict[str, Role]:
    existing = {
        role.key: role for role in (await db.execute(select(Role))).scalars().all()
    }
    for definition in ROLE_DEFINITIONS:
        role = existing.get(definition.key)
        if role is None:
            role = Role(
                key=definition.key,
                name=definition.name,
                description=definition.description,
                is_system=definition.is_system,
                is_superuser=definition.is_superuser,
                sort_order=definition.sort_order,
            )
            db.add(role)
            existing[definition.key] = role
            logger.info("seed.role.created", extra={"role": definition.key})
        else:
            # Keep descriptive metadata in step with the registry, but never
            # touch permissions -- those may have been customised.
            role.name = definition.name
            role.description = definition.description
            role.is_system = definition.is_system
            role.is_superuser = definition.is_superuser
            role.sort_order = definition.sort_order
    await db.flush()
    return existing


async def sync_modules(db: AsyncSession) -> dict[str, Module]:
    existing = {
        module.key: module for module in (await db.execute(select(Module))).scalars().all()
    }
    for definition in MODULE_DEFINITIONS:
        module = existing.get(definition.key)
        if module is None:
            module = Module(
                key=definition.key,
                name=definition.name,
                description=definition.description,
                icon=definition.icon,
                route=definition.route,
                sort_order=definition.sort_order,
                is_core=definition.is_core,
                is_implemented=definition.is_implemented,
                is_active=True,
            )
            db.add(module)
            existing[definition.key] = module
            logger.info("seed.module.created", extra={"module_key": definition.key})
        else:
            module.name = definition.name
            module.description = definition.description
            module.icon = definition.icon
            module.route = definition.route
            module.sort_order = definition.sort_order
            module.is_core = definition.is_core
            module.is_implemented = definition.is_implemented
    await db.flush()
    return existing


async def sync_default_permissions(
    db: AsyncSession, roles: dict[str, Role], modules: dict[str, Module]
) -> None:
    """Apply registry defaults only where no grant row exists yet.

    Existing rows are left alone so an administrator's changes survive
    redeployment.
    """
    rows = (await db.execute(select(RoleModulePermission))).scalars().all()
    seen = {(row.role_id, row.module_id) for row in rows}

    for definition in MODULE_DEFINITIONS:
        module = modules[definition.key]
        for role_key, level in definition.defaults.items():
            role = roles.get(role_key)
            if role is None or level is AccessLevel.NONE:
                continue
            if (role.id, module.id) in seen:
                continue
            db.add(
                RoleModulePermission(
                    role_id=role.id, module_id=module.id, access_level=level
                )
            )
            logger.info(
                "seed.permission.created",
                extra={"role": role_key, "module_key": definition.key, "access_level": level.value},
            )
    await db.flush()


async def ensure_bootstrap_admin(db: AsyncSession, roles: dict[str, Role]) -> str | None:
    """Create the initial Super Admin if no user exists at all.

    Returns the generated password when one was generated, so the operator can
    read it from the seed output exactly once.
    """
    user_count = len((await db.execute(select(User.id).limit(1))).scalars().all())
    if user_count:
        return None

    email = settings.bootstrap_admin_email.strip().lower()
    generated: str | None = None
    password = settings.bootstrap_admin_password
    if not password:
        password = generate_temporary_password()
        generated = password

    user = User(
        email=email,
        first_name=settings.bootstrap_admin_first_name,
        last_name=settings.bootstrap_admin_last_name,
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
        # Always true: the operator must replace the bootstrap credential.
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=roles[ROLE_SUPER_ADMIN].id))
    logger.info("seed.bootstrap_admin.created", extra={"email": email})
    return generated


async def seed() -> None:
    configure_logging()
    async with SessionFactory() as db:
        roles = await sync_roles(db)
        modules = await sync_modules(db)
        await sync_default_permissions(db, roles, modules)
        generated_password = await ensure_bootstrap_admin(db, roles)
        await db.commit()

    if generated_password:
        # Printed to stdout, not the structured log, and shown only once.
        print("=" * 72, file=sys.stderr)
        print("BOOTSTRAP SUPER ADMIN CREATED", file=sys.stderr)
        print(f"  Email:    {settings.bootstrap_admin_email}", file=sys.stderr)
        print(f"  Password: {generated_password}", file=sys.stderr)
        print("  You must change this password at first sign-in.", file=sys.stderr)
        print("=" * 72, file=sys.stderr)

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(seed())
