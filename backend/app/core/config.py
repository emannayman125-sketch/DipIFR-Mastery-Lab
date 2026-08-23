from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    app_name: str = "DipIFR Mastery Lab API"
    database_url: str = "sqlite:///./dipifr.db"
    secret_key: str = INSECURE_DEFAULT_SECRET
    access_token_minutes: int = 30
    refresh_token_days: int = 14
    reset_token_minutes: int = 30
    verification_token_hours: int = 24
    cors_origins: str = "http://localhost:3000"
    environment: str = "development"
    rate_limit_auth: str = "10/minute"
    rate_limit_tutor: str = "20/hour"
    frontend_url: str = "http://localhost:3000"
    refresh_cookie_name: str = "dipifr_refresh_token"
    cookie_domain: str | None = None
    refresh_cookie_samesite: str = "lax"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def validate_runtime(self) -> None:
        """Fail fast instead of silently running with an insecure secret in production."""
        if self.environment.lower() in {"production", "prod"}:
            if self.secret_key == INSECURE_DEFAULT_SECRET or len(self.secret_key) < 32:
                raise RuntimeError(
                    "SECRET_KEY must be a random value of at least 32 characters in production."
                )
            if self.database_url.startswith("sqlite"):
                                raise RuntimeError("Production must use PostgreSQL (or another server database), not SQLite.")
