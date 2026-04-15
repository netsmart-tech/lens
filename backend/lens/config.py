"""Pydantic Settings — loaded from environment (see .env.development at repo root)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # --- App ---
    environment: str = "development"
    log_format: str = "console"  # "console" or "json"

    # --- DB ---
    database_url: str = "postgresql+asyncpg://lens:lens_dev_password@db:5432/lens"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 10

    # --- CORS ---
    cors_origins: str = "http://localhost:3101"

    # --- Sessions ---
    session_secret: str = "dev-session-secret-change-me"
    session_cookie_name: str = "lens_session"
    session_max_age_hours: int = 12

    # --- OIDC (Authentik) ---
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://localhost:8101/api/auth/callback"
    oidc_authorize_url: str = "https://auth.netsmart.tech/application/o/authorize/"
    oidc_token_url: str = "https://auth.netsmart.tech/application/o/token/"
    oidc_userinfo_url: str = "https://auth.netsmart.tech/application/o/userinfo/"
    oidc_frontend_url: str = "http://localhost:3101/"
    oidc_scopes: str = "openid email profile"

    # --- Dev auth bypass ---
    lens_dev_auth: bool = False
    lens_dev_user_email: str = "sjensen@netsmart.tech"
    lens_dev_user_name: str = "Steve Jensen"

    # --- Secrets proxy ---
    secrets_proxy_url: str = ""
    secrets_proxy_client_cert: str = ""
    secrets_proxy_client_key: str = ""
    secrets_proxy_cache_ttl_s: int = 300

    # --- Sync workers ---
    jira_rate_limit_rps: int = 9
    jira_rate_limit_period_s: float = 1.0
    stale_threshold_s: int = 900  # 15 min — for sync envelope 'stale' state

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
