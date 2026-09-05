"""Application configuration.

Every setting is sourced from the environment (or a local ``.env`` file) so that
no secret ever needs to live in source control.  See ``docs/ENVIRONMENT.md`` for
the authoritative description of each variable.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]


class SMTPSettings(BaseSettings):
    """SMTP configuration structure.

    Phase 1 deliberately does NOT perform real SMTP delivery -- see
    ``app/services/email``.  The configuration surface exists so that operators
    can supply credentials later without any code change.
    """

    model_config = SettingsConfigDict(env_prefix="SMTP_", extra="ignore")

    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    # "none" | "starttls" | "ssl"
    secure: Literal["none", "starttls", "ssl"] = "starttls"
    from_email: str = "no-reply@example.internal"
    from_name: str = "Global Infrastructure"

    @property
    def is_configured(self) -> bool:
        """True once an operator has supplied the minimum viable SMTP config."""
        return bool(self.host and self.from_email)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    # -- Application -------------------------------------------------------
    app_name: str = "Global Infrastructure"
    environment: Environment = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Public base URL of the *frontend*, used to build password-reset links.
    frontend_base_url: str = "http://localhost:8080"

    # -- Database ----------------------------------------------------------
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://ght:ght@localhost:5434/ght",
    )
    database_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 10

    # -- Redis -------------------------------------------------------------
    # Used for rate limiting and access-token revocation. The application
    # degrades gracefully (in-process fallback) when Redis is unreachable.
    redis_url: str = "redis://localhost:6380/0"
    redis_enabled: bool = True

    # -- Security / tokens -------------------------------------------------
    # MUST be overridden in production. Validated below.
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    password_reset_ttl_minutes: int = 30

    # Cookie behaviour
    cookie_domain: str | None = None
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    refresh_cookie_name: str = "ght_refresh"
    csrf_cookie_name: str = "ght_csrf"
    csrf_header_name: str = "X-CSRF-Token"

    # -- Password policy ---------------------------------------------------
    password_min_length: int = 12
    password_max_length: int = 128
    password_require_upper: bool = True
    password_require_lower: bool = True
    password_require_digit: bool = True
    password_require_symbol: bool = True
    password_history_depth: int = 3

    # -- Argon2id cost -----------------------------------------------------
    # Defaults follow OWASP guidance. Lowered only in the test environment so
    # the suite is not dominated by deliberate key-stretching work; production
    # values are floor-checked in the validator below.
    password_hash_time_cost: int = 3
    password_hash_memory_cost_kib: int = 65536  # 64 MiB
    password_hash_parallelism: int = 1

    # -- Account lockout ---------------------------------------------------
    max_failed_logins: int = 5
    lockout_minutes: int = 15

    # -- Rate limits (requests / window seconds) ---------------------------
    rate_limit_login: str = "10/60"
    rate_limit_forgot_password: str = "5/900"
    rate_limit_reset_password: str = "10/900"
    rate_limit_default: str = "300/60"

    # -- CORS --------------------------------------------------------------
    # Held as a raw string because pydantic-settings JSON-decodes complex types
    # read from a dotenv file, which would reject a plain comma-separated list.
    # Consumers use the `cors_origins` property below.
    cors_origins_raw: str = Field(
        default="http://localhost:8080,http://localhost:5174",
        alias="CORS_ORIGINS",
    )

    # -- Email -------------------------------------------------------------
    # "log"  -> render the message to the application log (Phase 1 default)
    # "smtp" -> real delivery; NOT implemented in Phase 1 (see docs/SMTP.md)
    email_transport: Literal["log", "smtp"] = "log"
    smtp: SMTPSettings = Field(default_factory=SMTPSettings)

    # Where the log transport writes full message bodies for developers.
    # Never written to in production -- see app/services/email/outbox.py.
    dev_outbox_dir: str = "var/dev-outbox"

    # -- Bootstrap superadmin (seed only) ----------------------------------
    bootstrap_admin_email: str = "superadmin@example.internal"
    bootstrap_admin_password: str = ""
    bootstrap_admin_first_name: str = "Super"
    bootstrap_admin_last_name: str = "Admin"

    @model_validator(mode="after")
    def _enforce_production_hardening(self) -> "Settings":
        if self.environment == "production":
            problems: list[str] = []
            if self.jwt_secret == "dev-insecure-secret-change-me" or len(self.jwt_secret) < 32:
                problems.append("JWT_SECRET must be set to a random value of >=32 characters")
            if not self.cookie_secure:
                problems.append("COOKIE_SECURE must be true in production")
            if self.debug:
                problems.append("DEBUG must be false in production")
            # OWASP minimum for Argon2id: 19 MiB memory, 2 iterations.
            if self.password_hash_memory_cost_kib < 19456:
                problems.append("PASSWORD_HASH_MEMORY_COST_KIB must be >= 19456 (19 MiB)")
            if self.password_hash_time_cost < 2:
                problems.append("PASSWORD_HASH_TIME_COST must be >= 2")
            if problems:
                raise ValueError(
                    "Refusing to start in production with insecure configuration: "
                    + "; ".join(problems)
                )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def sync_database_url(self) -> str:
        """Alembic runs synchronously; strip the asyncpg driver suffix."""
        return str(self.database_url).replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
