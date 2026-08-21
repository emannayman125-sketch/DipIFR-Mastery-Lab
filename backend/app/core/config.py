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
    # Cookie domain for the refresh-token cookie (unset = current host only).
    cookie_domain: str | None = None
    # "lax" works for local dev (frontend/backend are same-site, different
    # ports). If the frontend and backend are deployed on different sites
    # (e.g. Vercel + a separate API host, as in this project's deployment
    # architecture), a cross-site fetch() will NOT attach a Lax cookie —
    # set this to "none" in that environment (requires cookie_secure=True,
    # which is automatic outside development/test).
    refresh_cookie_samesite: str = "lax"

    # Optional: set to enable the real AI tutor + AI-assisted grading.
    # Without it, the tutor and grading fall back to clearly-labelled
    # rule-based behaviour instead of failing.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

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
            if "localhost:3000" in self.cors_origins:
                raise RuntimeError("Replace localhost CORS_ORIGINS with the production frontend origin.")
            if self.refresh_cookie_samesite.lower() not in {"lax", "strict", "none"}:
                raise RuntimeError("REFRESH_COOKIE_SAMESITE must be 'lax', 'strict', or 'none'.")

    @property
    def cookie_secure(self) -> bool:
        """Refresh-token cookie must be Secure (HTTPS-only) outside local dev/test,
        where the frontend is typically served over plain http://localhost."""
        return self.environment.lower() not in {"development", "test"}


settings = Settings()
