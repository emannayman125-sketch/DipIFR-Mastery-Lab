"""Tests for Settings.validate_runtime() — the fail-fast checks that stop
the app from starting in production with an insecure or incomplete
configuration. These construct Settings directly (not via env vars) so they
can't be affected by, or leak into, the test-environment defaults set in
conftest.py.
"""
import pytest

from app.core.config import Settings

VALID_PROD_KWARGS = dict(
    environment="production",
    secret_key="a" * 40,
    database_url="postgresql+psycopg://user:pass@host:5432/db",
    cors_origins="https://app.example.com",
    refresh_cookie_samesite="none",
    smtp_host="smtp.example.com",
    smtp_from_email="noreply@example.com",
)


def test_valid_production_config_passes():
    Settings(**VALID_PROD_KWARGS).validate_runtime()  # should not raise


def test_production_rejects_default_secret():
    kwargs = {**VALID_PROD_KWARGS, "secret_key": "change-me-in-production"}
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings(**kwargs).validate_runtime()


def test_production_rejects_short_secret():
    kwargs = {**VALID_PROD_KWARGS, "secret_key": "short"}
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings(**kwargs).validate_runtime()


def test_production_rejects_sqlite():
    kwargs = {**VALID_PROD_KWARGS, "database_url": "sqlite:///./dipifr.db"}
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        Settings(**kwargs).validate_runtime()


def test_production_rejects_localhost_cors():
    kwargs = {**VALID_PROD_KWARGS, "cors_origins": "http://localhost:3000"}
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        Settings(**kwargs).validate_runtime()


def test_production_rejects_invalid_samesite():
    kwargs = {**VALID_PROD_KWARGS, "refresh_cookie_samesite": "bogus"}
    with pytest.raises(RuntimeError, match="REFRESH_COOKIE_SAMESITE"):
        Settings(**kwargs).validate_runtime()


def test_production_rejects_missing_smtp_host():
    kwargs = {**VALID_PROD_KWARGS, "smtp_host": None}
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        Settings(**kwargs).validate_runtime()


def test_production_rejects_missing_smtp_from_email():
    kwargs = {**VALID_PROD_KWARGS, "smtp_from_email": None}
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        Settings(**kwargs).validate_runtime()


def test_development_does_not_require_smtp():
    Settings(environment="development").validate_runtime()  # should not raise
