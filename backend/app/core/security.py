"""Password hashing, password policy, and opaque-token primitives.

Design notes
------------
* Hashing uses **Argon2id** (OWASP's first recommendation) via ``argon2-cffi``.
  The hasher is wrapped so the algorithm can be swapped later without touching
  call sites, and ``needs_rehash`` lets us transparently upgrade parameters.
* Refresh tokens and password-reset tokens are *opaque random strings*.  Only a
  SHA-256 digest is persisted, so a database disclosure does not yield usable
  tokens.  Lookups are by digest, which is why SHA-256 (fast, indexable) is
  correct here rather than a slow password hash.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError, VerificationError

from app.core.config import settings

# Parameters come from settings so the test suite can use a cheap cost without
# weakening production, where the values are floor-checked at startup.
_hasher = PasswordHasher(
    time_cost=settings.password_hash_time_cost,
    memory_cost=settings.password_hash_memory_cost_kib,
    parallelism=settings.password_hash_parallelism,
    hash_len=32,
    salt_len=16,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Return an encoded Argon2id hash. The plaintext is never retained."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-time-ish verification that never raises on malformed input."""
    if not password_hash:
        # Still burn CPU so a user without a hash is not distinguishable by
        # response time from one with a hash.
        _hasher.hash(password)
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


# ---------------------------------------------------------------------------
# Password policy
# ---------------------------------------------------------------------------

_SYMBOLS = set(string.punctuation)

# Rejected outright regardless of the character-class rules.
_COMMON_PASSWORDS = {
    "password", "password1", "password123", "passw0rd", "administrator",
    "qwerty123456", "123456789012", "letmein12345", "welcome12345",
    "changeme1234", "admin1234567", "iloveyou1234",
}


def validate_password_strength(password: str, *, email: str | None = None) -> list[str]:
    """Return a list of human-readable policy violations (empty == acceptable)."""
    problems: list[str] = []

    if len(password) < settings.password_min_length:
        problems.append(f"Must be at least {settings.password_min_length} characters long.")
    if len(password) > settings.password_max_length:
        problems.append(f"Must be at most {settings.password_max_length} characters long.")
    if settings.password_require_lower and not any(c.islower() for c in password):
        problems.append("Must contain a lowercase letter.")
    if settings.password_require_upper and not any(c.isupper() for c in password):
        problems.append("Must contain an uppercase letter.")
    if settings.password_require_digit and not any(c.isdigit() for c in password):
        problems.append("Must contain a digit.")
    if settings.password_require_symbol and not any(c in _SYMBOLS for c in password):
        problems.append("Must contain a special character.")
    if password.lower() in _COMMON_PASSWORDS:
        problems.append("This password is too common.")
    if email:
        local_part = email.split("@", 1)[0].lower()
        if local_part and len(local_part) >= 3 and local_part in password.lower():
            problems.append("Must not contain your email address.")

    return problems


def generate_temporary_password() -> str:
    """Generate an initial password that satisfies the configured policy.

    Used when an Admin creates a user or triggers an administrative reset. The
    account is always flagged ``must_change_password`` alongside this.
    """
    alphabet = string.ascii_letters + string.digits
    symbols = "!@#$%^&*?-_"
    length = max(settings.password_min_length, 16)
    while True:
        body = "".join(secrets.choice(alphabet) for _ in range(length - 2))
        candidate = (
            secrets.choice(string.ascii_uppercase)
            + body
            + secrets.choice(symbols)
        )
        if not validate_password_strength(candidate):
            return candidate


# ---------------------------------------------------------------------------
# Opaque tokens (refresh / password reset / CSRF)
# ---------------------------------------------------------------------------


def generate_token(num_bytes: int = 48) -> str:
    """Cryptographically secure, URL-safe token."""
    return secrets.token_urlsafe(num_bytes)


def hash_token(token: str) -> str:
    """SHA-256 digest used as the stored, indexable representation of a token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
