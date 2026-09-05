"""Security primitives: hashing, policy, redaction, rate limiting, headers."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.logging import redact
from app.core.rate_limit import client_identifier, parse_limit, rate_limit, reset_local_counters
from app.core.security import (
    generate_temporary_password,
    generate_token,
    hash_password,
    hash_token,
    validate_password_strength,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_is_not_the_plaintext(self):
        assert hash_password("Correct!Horse2026") != "Correct!Horse2026"

    def test_hash_is_salted(self):
        assert hash_password("Correct!Horse2026") != hash_password("Correct!Horse2026")

    def test_verification_round_trips(self):
        assert verify_password("Correct!Horse2026", hash_password("Correct!Horse2026"))

    def test_wrong_password_fails(self):
        assert not verify_password("Wrong!Horse2026", hash_password("Correct!Horse2026"))

    def test_missing_hash_is_handled_without_raising(self):
        assert verify_password("anything", None) is False

    def test_malformed_hash_is_handled_without_raising(self):
        assert verify_password("anything", "not-a-hash") is False

    def test_argon2id_is_used(self):
        assert hash_password("Correct!Horse2026").startswith("$argon2id$")


class TestPasswordPolicy:
    def test_a_compliant_password_passes(self):
        assert validate_password_strength("Str0ng!Passphrase") == []

    @pytest.mark.parametrize(
        "password",
        ["Sh0rt!A", "nouppercase1!", "NOLOWERCASE1!", "NoDigitsAtAll!", "NoSymbols12345"],
    )
    def test_non_compliant_passwords_are_rejected(self, password):
        assert validate_password_strength(password)

    def test_common_passwords_are_rejected(self):
        assert validate_password_strength("password123")

    def test_a_password_containing_the_email_is_rejected(self):
        problems = validate_password_strength(
            "Jsmith!Password1", email="jsmith@test.internal"
        )
        assert any("email" in problem for problem in problems)

    def test_generated_temporary_passwords_always_satisfy_the_policy(self):
        for _ in range(25):
            assert validate_password_strength(generate_temporary_password()) == []


class TestOpaqueTokens:
    def test_tokens_are_unique(self):
        assert len({generate_token() for _ in range(100)}) == 100

    def test_tokens_are_long_enough_to_resist_guessing(self):
        assert len(generate_token()) >= 43  # 32+ bytes of entropy, URL-safe

    def test_hashing_is_deterministic_and_one_way(self):
        token = generate_token()
        assert hash_token(token) == hash_token(token)
        assert token not in hash_token(token)
        assert len(hash_token(token)) == 64


class TestLogRedaction:
    def test_sensitive_keys_are_masked(self):
        cleaned = redact({"email": "a@b.c", "password": "hunter2", "token": "abc123"})
        assert cleaned["email"] == "a@b.c"
        assert cleaned["password"] == "***REDACTED***"
        assert cleaned["token"] == "***REDACTED***"

    def test_nested_structures_are_masked(self):
        cleaned = redact({"outer": {"inner": [{"refresh_token": "secret-value"}]}})
        assert "secret-value" not in str(cleaned)

    def test_inline_occurrences_in_strings_are_masked(self):
        assert "hunter2" not in redact("logging in with password=hunter2 now")

    def test_ordinary_values_survive_untouched(self):
        assert redact({"count": 3, "name": "Ada"}) == {"count": 3, "name": "Ada"}


class TestRateLimiting:
    def test_limit_specs_are_parsed(self):
        assert parse_limit("10/60") == (10, 60)
        assert parse_limit("5/900") == (5, 900)

    async def test_requests_beyond_the_limit_are_rejected(self):
        """Exercised directly: the endpoint limits are set high for the suite."""
        from app.core.errors import RateLimitedError

        reset_local_counters()
        dependency = rate_limit("unit-test-bucket", "3/60")

        class FakeRequest:
            headers: dict[str, str] = {}
            client = type("Client", (), {"host": "10.0.0.1"})()

        request = FakeRequest()
        for _ in range(3):
            await dependency(request)

        with pytest.raises(RateLimitedError) as excinfo:
            await dependency(request)
        assert excinfo.value.status_code == 429

    async def test_budgets_are_per_client(self):
        reset_local_counters()
        dependency = rate_limit("per-client-bucket", "1/60")

        def make(host: str):
            return type(
                "R", (), {"headers": {}, "client": type("C", (), {"host": host})()}
            )()

        await dependency(make("10.0.0.1"))
        await dependency(make("10.0.0.2"))  # a different caller is unaffected

    def test_forwarded_header_identifies_the_original_client(self):
        request = type(
            "R",
            (),
            {
                "headers": {"x-forwarded-for": "203.0.113.7, 10.0.0.1"},
                "client": type("C", (), {"host": "10.0.0.1"})(),
            },
        )()
        assert client_identifier(request) == "203.0.113.7"


class TestResponseHardening:
    async def test_security_headers_are_present(self, client):
        response = await client.get("/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "Cache-Control" in response.headers

    async def test_health_is_public(self, client):
        assert (await client.get("/health")).status_code == 200

    async def test_readiness_reports_dependencies(self, client):
        body = (await client.get("/health/ready")).json()
        assert body["checks"]["database"] == "ok"
        # Redis is disabled for the suite; the app must still be ready.
        assert body["status"] == "ready"

    async def test_password_policy_is_advertised(self, client):
        body = (await client.get("/api/v1/auth/password-policy")).json()
        assert body["min_length"] == settings.password_min_length


class TestProductionConfigGuards:
    """The app must refuse to start with insecure production settings."""

    def _settings(self, **overrides):
        from app.core.config import Settings

        base = {
            "environment": "production",
            "jwt_secret": "a" * 48,
            "cookie_secure": True,
            "debug": False,
            # The suite's cheap KDF cost lives in the environment; a production
            # config must supply real values, so state them explicitly here.
            "password_hash_time_cost": 3,
            "password_hash_memory_cost_kib": 65536,
        }
        return Settings(**{**base, **overrides})

    def test_a_hardened_production_config_is_accepted(self):
        assert self._settings().is_production

    def test_the_default_secret_is_refused(self):
        with pytest.raises(ValueError, match="JWT_SECRET"):
            self._settings(jwt_secret="dev-insecure-secret-change-me")

    def test_a_short_secret_is_refused(self):
        with pytest.raises(ValueError, match="JWT_SECRET"):
            self._settings(jwt_secret="too-short")

    def test_insecure_cookies_are_refused(self):
        with pytest.raises(ValueError, match="COOKIE_SECURE"):
            self._settings(cookie_secure=False)

    def test_debug_mode_is_refused(self):
        with pytest.raises(ValueError, match="DEBUG"):
            self._settings(debug=True)

    def test_a_weak_hash_cost_is_refused(self):
        with pytest.raises(ValueError, match="MEMORY_COST"):
            self._settings(password_hash_memory_cost_kib=1024)
