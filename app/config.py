"""Application configuration and environment validation."""
from functools import lru_cache
from typing import Any, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Values copied from .env.example / docs — never treat as real secrets.
_PLACEHOLDER_VALUES = frozenset(
    {
        "your_telegram_bot_token_here",
        "your_openai_api_key_here",
        "your_44_character_fernet_key_here",
        "your_garmin_consumer_key",
        "your_garmin_consumer_secret",
        "change_me_to_a_strong_password",
        "changeme",
        "password",
        "test",
    }
)


def _is_placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    if not normalized:
        return True
    if normalized in _PLACEHOLDER_VALUES:
        return True
    if normalized.startswith("your_") and normalized.endswith("_here"):
        return True
    return False


def _optional_secret(value: Any) -> Optional[str]:
    if value is None or _is_placeholder(value):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


class Settings(BaseSettings):
    """Application settings with environment variable validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram — ignored by API unless you run the bot profile
    telegram_bot_token: Optional[str] = Field(default=None)

    # OpenAI — optional at startup; required when using /web/chat
    openai_api_key: Optional[str] = Field(default=None)

    # Database (optional — built from DB_* in database.py when empty)
    database_url: Optional[str] = Field(default=None)
    db_user: Optional[str] = Field(default=None)
    db_password: Optional[str] = Field(default=None)
    db_host: Optional[str] = Field(default=None)
    db_port: Optional[str] = Field(default=None)
    db_name: Optional[str] = Field(default=None)

    # Security
    encryption_key: str

    # Garmin
    garmin_consumer_key: Optional[str] = Field(default=None)
    garmin_consumer_secret: Optional[str] = Field(default=None)
    garmin_redirect_uri: Optional[str] = Field(default=None)
    webapp_url: str = Field(default="http://localhost:8000")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="Comma-separated allowed CORS origins",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @field_validator("encryption_key", mode="before")
    @classmethod
    def validate_encryption_key(cls, v: Any) -> str:
        if _is_placeholder(v):
            raise ValueError(
                "ENCRYPTION_KEY is not set. Generate with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        if not isinstance(v, str) or not v.strip():
            raise ValueError("ENCRYPTION_KEY cannot be empty")
        key = v.strip()
        if len(key) != 44:
            raise ValueError("ENCRYPTION_KEY must be 44 characters long (Fernet key).")
        return key

    @field_validator("telegram_bot_token", mode="before")
    @classmethod
    def normalize_telegram_token(cls, v: Any) -> Optional[str]:
        token = _optional_secret(v)
        if token is None:
            return None
        # Real Telegram bot tokens look like 123456789:AAH...
        if ":" not in token:
            return None
        return token

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def normalize_openai_key(cls, v: Any) -> Optional[str]:
        return _optional_secret(v)

    @field_validator("garmin_consumer_key", "garmin_consumer_secret", mode="before")
    @classmethod
    def normalize_garmin_credentials(cls, v: Any) -> Optional[str]:
        return _optional_secret(v)

    @field_validator("garmin_redirect_uri", mode="before")
    @classmethod
    def validate_garmin_redirect_uri(cls, v: Any) -> Optional[str]:
        uri = _optional_secret(v)
        if uri and not uri.startswith("https://"):
            raise ValueError("GARMIN_REDIRECT_URI must start with https://")
        return uri

    @field_validator("webapp_url", mode="before")
    @classmethod
    def validate_webapp_url(cls, v: Any) -> str:
        if _is_placeholder(v):
            return "http://localhost:8000"
        if not isinstance(v, str) or not v.strip():
            return "http://localhost:8000"
        url = v.strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("WEBAPP_URL must start with http:// or https://")
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
