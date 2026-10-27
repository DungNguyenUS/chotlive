from __future__ import annotations

import base64
import hashlib
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"  # development | test | production
    APP_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "sqlite:///./chotlive_dev.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "dev-only-jwt-secret-key-change-in-production-32chars"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ENCRYPTION_KEY: str = ""

    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_REDIRECT_URI: str = "http://localhost:8000/api/v1/meta/oauth/callback"
    META_API_VERSION: str = "v21.0"
    META_WEBHOOK_VERIFY_TOKEN: str = "chotlive_dev_verify_token"
    # Extra OAuth scopes (comma-separated), e.g. "pages_read_user_content" once it is added in the Meta App dashboard
    META_OAUTH_EXTRA_SCOPES: str = ""
    ALLOW_MOCK_META_IN_DEV: bool = True

    PRINT_BRIDGE_URL: str = "http://127.0.0.1:9100"
    PRINT_BRIDGE_TIMEOUT_SECONDS: int = 5

    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 180

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def allow_mock_provider(self) -> bool:
        if self.is_production:
            return False
        return self.ALLOW_MOCK_META_IN_DEV

    @property
    def has_real_meta_credentials(self) -> bool:
        return bool(self.META_APP_ID.strip() and self.META_APP_SECRET.strip())

    @property
    def cors_origin_list(self) -> List[str]:
        origins = [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.FRONTEND_URL.strip():
            fe = self.FRONTEND_URL.strip().rstrip("/")
            if fe not in origins:
                origins.append(fe)
        return origins

    @property
    def normalized_database_url(self) -> str:
        """
        Automatically converts Render/Heroku style `postgres://` or `postgresql://` URLs
        into SQLAlchemy 2.x psycopg v3 format `postgresql+psycopg://`.
        """
        url = self.DATABASE_URL.strip()
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://") and "+psycopg" not in url:
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def fernet_key(self) -> bytes:
        raw = self.ENCRYPTION_KEY.strip()
        if raw and raw != "REPLACE_WITH_VALID_32_BYTE_BASE64_FERNET_KEY":
            try:
                decoded = base64.urlsafe_b64decode(raw.encode("utf-8"))
                if len(decoded) == 32:
                    return raw.encode("utf-8")
            except Exception:
                pass
        digest = hashlib.sha256(self.SECRET_KEY.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)


settings = Settings()
