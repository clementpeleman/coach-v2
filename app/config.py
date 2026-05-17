"""Application configuration and environment validation."""
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram (optional — webapp-only deployments skip this)
    telegram_bot_token: Optional[str] = Field(default=None)

    # OpenAI (optional at startup; required when using /web/chat)
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

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        if not v:
            raise ValueError("ENCRYPTION_KEY cannot be empty")
        if len(v) != 44:
            raise ValueError(
                "ENCRYPTION_KEY must be 44 characters long. "
                "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        return v

    @field_validator("telegram_bot_token", mode="before")
    @classmethod
    def empty_telegram_token_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, str) and ":" not in v:
            return None
        return v

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def empty_openai_key_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("garmin_redirect_uri")
    @classmethod
    def validate_garmin_redirect_uri(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith("https://"):
            raise ValueError("GARMIN_REDIRECT_URI must start with https://")
        return v

    @field_validator("webapp_url")
    @classmethod
    def validate_webapp_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("WEBAPP_URL must start with http:// or https://")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Backwards-compatible module-level accessor
settings = get_settings()
