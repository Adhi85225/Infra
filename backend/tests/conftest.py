"""Test harness.

Environment variables are set *before* any application import so that the
cached ``Settings`` singleton picks up the test configuration.

The suite runs against a real PostgreSQL database (``<db>_test``) created on the
fly and migrated with Alembic -- so every run also verifies that the migrations
actually produce the schema the code expects.  Redis is disabled, which exercises
the in-process fallbacks.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

# --- Test configuration (must precede app imports) -------------------------
_base_url = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://ght:change-me-in-production@localhost:5434/ght"
)
_parts = urlsplit(_base_url)
_test_db_name = (_parts.path.lstrip("/") or "ght") + "_test"
TEST_DATABASE_URL = urlunsplit(
    (_parts.scheme, _parts.netloc, f"/{_test_db_name}", _parts.query, _parts.fragment)
)
ADMIN_DATABASE_URL = urlunsplit(
    (_parts.scheme, _parts.netloc, "/postgres", _parts.query, _parts.fragment)
)

os.environ.update(
    ENVIRONMENT="test",
    DEBUG="false",
    DATABASE_URL=TEST_DATABASE_URL,
    REDIS_ENABLED="false",
    JWT_SECRET="test-only-secret-value-that-is-long-enough-32",
    COOKIE_SECURE="false",
    EMAIL_TRANSPORT="log",
    # Generous so ordinary tests never trip the limiter; the limiter itself is
    # tested directly in tests/test_rate_limit.py.
    RATE_LIMIT_LOGIN="1000/60",
    RATE_LIMIT_FORGOT_PASSWORD="1000/60",
    RATE_LIMIT_RESET_PASSWORD="1000/60",
    MAX_FAILED_LOGINS="5",
    LOCKOUT_MINUTES="15",
    DEV_OUTBOX_DIR="var/test-outbox",
    # Cheap KDF cost: the suite hashes hundreds of passwords and is not
    # measuring key-stretching. Production floors are enforced separately.
    PASSWORD_HASH_TIME_COST="1",
    PASSWORD_HASH_MEMORY_COST_KIB="8192",
)

import asyncio  # noqa: E402
import shutil  # noqa: E402
from collections.abc import AsyncGenerator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
import sqlalchemy as sa  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.rate_limit import reset_local_counters  # noqa: E402
from app.db.seed import (  # noqa: E402
    sync_default_permissions,
    sync_modules,
    sync_roles,
)
from app.main import create_app  # noqa: E402
from app.models import Base, Role, User, UserRole  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.enums import UserStatus  # noqa: E402

# Passwords used across the suite. Deliberately satisfy the default policy.
SUPERADMIN_PASSWORD = "SuperAdmin!Pass2026"
ADMIN_PASSWORD = "AdminUser!Pass2026"
USER_PASSWORD = "NormalUser!Pass2026"
GUEST_PASSWORD = "GuestUser!Pass2026"


# ---------------------------------------------------------------------------
# Database lifecycle
# ---------------------------------------------------------------------------


async def _recreate_test_database() -> None:
    engine = create_async_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(
            sa.text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": _test_db_name},
        )
        await conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{_test_db_name}"'))
        await conn.execute(sa.text(f'CREATE DATABASE "{_test_db_name}"'))
    await engine.dispose()


def _run_migrations() -> None:
    """Apply Alembic migrations to the freshly created test database."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    asyncio.run(_recreate_test_database())
    _run_migrations()
    yield
    outbox = Path(settings.dev_outbox_dir)
    if outbox.exists():
        shutil.rmtree(outbox, ignore_errors=True)


# Every table is reset between tests, and the catalogue is re-seeded.
#
# Nothing here is treated as static: tests legitimately create custom roles,
# deactivate a module and add a module, so leaving any of it in place lets one
# test change the outcome of another.
_VOLATILE_TABLES = (
    "audit_logs",
    "password_history",
    "password_reset_tokens",
    "sessions",
    "user_roles",
    "role_module_permissions",
    "users",
    "roles",
    "modules",
)


@pytest.fixture
async def engine():
    """A fresh engine per test.

    pytest-asyncio gives each test its own event loop, and asyncpg connections
    are bound to the loop that created them -- so a session-scoped engine would
    eventually hand out a connection attached to a closed loop. The engine is
    therefore per-test and disposed afterwards. Pooling stays *on* within that
    scope so a test's many requests reuse one connection.
    """
    engine = create_async_engine(TEST_DATABASE_URL)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    """A clean, seeded database for every test."""
    reset_local_counters()

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        tables = ", ".join(f'"{name}"' for name in _VOLATILE_TABLES)
        await session.execute(sa.text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

        # Re-seed the catalogue the truncate cleared, exactly as a fresh
        # deployment would.
        roles = await sync_roles(session)
        modules = await sync_modules(session)
        await sync_default_permissions(session, roles, modules)
        await session.commit()

        yield session


@pytest.fixture(scope="session")
def app():
    """One application instance for the whole suite.

    Building a FastAPI app is not cheap and the app holds no per-test state --
    only the database dependency varies, and that is overridden per test below.
    """
    return create_app()


@pytest.fixture
async def client(db, engine, app) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client bound to the app, sharing the test database engine."""
    from app.core.database import get_session

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------


async def create_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    role_keys: list[str],
    status: UserStatus = UserStatus.ACTIVE,
    must_change_password: bool = False,
    first_name: str = "Test",
    last_name: str = "User",
) -> User:
    user = User(
        email=email.lower(),
        first_name=first_name,
        last_name=last_name,
        password_hash=hash_password(password),
        status=status,
        must_change_password=must_change_password,
    )
    db.add(user)
    await db.flush()

    for key in role_keys:
        role = (await db.execute(sa.select(Role).where(Role.key == key))).scalar_one()
        db.add(UserRole(user_id=user.id, role_id=role.id))

    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def superadmin(db) -> User:
    return await create_user(
        db,
        email="superadmin@test.internal",
        password=SUPERADMIN_PASSWORD,
        role_keys=["SUPER_ADMIN"],
        first_name="Super",
    )


@pytest.fixture
async def admin(db) -> User:
    return await create_user(
        db, email="admin@test.internal", password=ADMIN_PASSWORD, role_keys=["ADMIN"],
        first_name="Admin",
    )


@pytest.fixture
async def normal_user(db) -> User:
    return await create_user(
        db, email="user@test.internal", password=USER_PASSWORD, role_keys=["USER"],
        first_name="Normal",
    )


@pytest.fixture
async def guest(db) -> User:
    return await create_user(
        db, email="guest@test.internal", password=GUEST_PASSWORD, role_keys=["GUEST"],
        first_name="Guest",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def login(client: AsyncClient, email: str, password: str):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def auth_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    response = await login(client, email, password)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def refetch(db: AsyncSession, model, pk):
    """Re-read a row, ignoring the session's identity map.

    The API writes through its own session, so an object already loaded in the
    test's session would otherwise still show pre-request values.
    """
    db.expire_all()
    return (await db.execute(sa.select(model).where(model.id == pk))).scalar_one()


def read_outbox_token(email: str) -> str | None:
    """Extract the newest password-reset token addressed to ``email``."""
    directory = Path(settings.dev_outbox_dir)
    if not directory.exists():
        return None
    files = sorted(directory.glob(f"*_{email.replace('@', '_').replace('.', '_')}*.txt"))
    if not files:
        files = sorted(p for p in directory.glob("*.txt") if email in p.read_text())
    if not files:
        return None
    body = files[-1].read_text()
    marker = "token="
    index = body.rfind(marker)
    if index == -1:
        return None
    return body[index + len(marker) :].split()[0].strip()
