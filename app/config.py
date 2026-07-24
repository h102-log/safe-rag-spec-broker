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
    judge_model: str = "claude-sonnet-5"
    # ponytail: 임계값 미캘리브레이션 — BGE-M3 cosine 분포 실측 전. C 페이즈(RAGAS)에서 튜닝.
    no_context_threshold: float = 0.4

    # LLM / 관측 키 — 없어도 로컬 개발/테스트가 가능해야 하므로 옵셔널.
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
