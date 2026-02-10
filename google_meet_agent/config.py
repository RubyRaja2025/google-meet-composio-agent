"""Configuration management using Pydantic settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields in .env
    )

    # Composio settings
    composio_api_key: str

    # Anthropic settings
    anthropic_api_key: str
    model_name: str = "claude-sonnet-4-20250514"

    # Entity ID (user identifier in Composio)
    # Each user should have a unique entity_id
    google_meet_user_id: str = "default"

    # Agent settings
    agent_max_turns: int = 10

    # OAuth settings
    oauth_timeout: int = 300  # seconds to wait for user to complete OAuth

    # Retry settings
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
