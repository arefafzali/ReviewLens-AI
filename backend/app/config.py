"""Application configuration and environment-driven settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="REVIEWLENS_",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = Field(
        ...,
        description="Runtime environment name.",
    )
    api_host: str = Field("0.0.0.0", description="HTTP bind host.")
    api_port: int = Field(8000, ge=1, le=65535, description="HTTP bind port.")
    api_prefix: str = Field("", description="Global API path prefix.")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = {"local", "development", "staging", "production", "test"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            allowed_values = ", ".join(sorted(allowed))
            raise ValueError(f"environment must be one of: {allowed_values}")
        return normalized


@lru_cache

def get_settings() -> Settings:
    """Return cached validated settings.

    Loading settings at app startup ensures fail-fast behavior when required
    environment variables are missing or invalid.
    """

    return Settings()
