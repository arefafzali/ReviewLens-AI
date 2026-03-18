"""Application configuration and environment-driven settings."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
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
    database_url: str = Field(
        ...,
        validation_alias=AliasChoices("REVIEWLENS_DATABASE_URL", "DATABASE_URL"),
        description="Database connection URL.",
    )
    firecrawl_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REVIEWLENS_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"),
        description="Firecrawl API key for public URL fetching.",
    )
    firecrawl_timeout_seconds: float = Field(
        default=45.0,
        validation_alias=AliasChoices("REVIEWLENS_FIRECRAWL_TIMEOUT_SECONDS"),
        ge=1.0,
        le=120.0,
        description="Timeout for Firecrawl API requests.",
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REVIEWLENS_OPENAI_API_KEY", "OPENAI_API_KEY"),
        description="OpenAI API key for markdown chunk review extraction.",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("REVIEWLENS_OPENAI_MODEL"),
        description="OpenAI model used for markdown chunk review extraction.",
    )
    openai_timeout_seconds: float = Field(
        default=45.0,
        validation_alias=AliasChoices("REVIEWLENS_OPENAI_TIMEOUT_SECONDS"),
        ge=1.0,
        le=120.0,
        description="Timeout for OpenAI extraction calls.",
    )
    markdown_chunk_size_chars: int = Field(
        default=6000,
        validation_alias=AliasChoices("REVIEWLENS_MARKDOWN_CHUNK_SIZE_CHARS"),
        ge=500,
        le=30000,
        description="Chunk size for markdown slicing before GPT extraction.",
    )
    markdown_chunk_overlap_chars: int = Field(
        default=800,
        validation_alias=AliasChoices("REVIEWLENS_MARKDOWN_CHUNK_OVERLAP_CHARS"),
        ge=0,
        le=5000,
        description="Overlap between markdown chunks.",
    )
    markdown_max_chunks: int = Field(
        default=30,
        validation_alias=AliasChoices("REVIEWLENS_MARKDOWN_MAX_CHUNKS"),
        ge=1,
        le=100,
        description="Maximum markdown chunks to send to GPT per URL.",
    )
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
