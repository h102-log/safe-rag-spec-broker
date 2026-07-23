"""환경변수 로더 (.env). pydantic-settings 기반."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    embedding_model: str = "BAAI/bge-m3"
    generation_model: str = "claude-opus-4-8"

    # LLM / 관측 키 — 없어도 로컬 개발/테스트가 가능해야 하므로 옵셔널.
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
