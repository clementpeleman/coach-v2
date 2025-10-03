"""Application configuration and environment validation."""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings with environment variable validation."""

    # Telegram Configuration
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")

    # OpenAI Configuration
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")

    # Database Configuration (optional - can use individual DB_* variables instead)
    database_url: Optional[str] = Field(default=None, env="DATABASE_URL")
    db_user: Optional[str] = Field(default=None, env="DB_USER")
    db_password: Optional[str] = Field(default=None, env="DB_PASSWORD")
    db_host: Optional[str] = Field(default=None, env="DB_HOST")
    db_port: Optional[str] = Field(default=None, env="DB_PORT")
    db_name: Optional[str] = Field(default=None, env="DB_NAME")

    # Security Configuration
    encryption_key: str = Field(..., env="ENCRYPTION_KEY")

    # Garmin Configuration (optional for development)
    garmin_consumer_key: Optional[str] = Field(default=None, env="GARMIN_CONSUMER_KEY")
    garmin_consumer_secret: Optional[str] = Field(default=None, env="GARMIN_CONSUMER_SECRET")

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """Validate that encryption key is properly formatted for Fernet."""
        if not v:
            raise ValueError("ENCRYPTION_KEY cannot be empty")
        # Fernet keys should be 44 characters (32 bytes base64 encoded)
        if len(v) != 44:
            raise ValueError(
                "ENCRYPTION_KEY must be 44 characters long. "
                "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        return v

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_telegram_token(cls, v: str) -> str:
        """Validate Telegram bot token format."""
        if not v or ":" not in v:
            raise ValueError("Invalid TELEGRAM_BOT_TOKEN format")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False


def validate_environment() -> Settings:
    """
    Validate all required environment variables are present and properly formatted.

    Returns:
        Settings object with validated configuration

    Raises:
        ValueError: If any required environment variable is missing or invalid
    """
    try:
        settings = Settings()
        return settings
    except Exception as e:
        raise ValueError(f"Environment validation failed: {e}")


# Global settings instance
settings = validate_environment()
