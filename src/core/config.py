"""Central settings. Everything configurable lives here, loaded from .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    # EDGAR — SEC requires a descriptive User-Agent with contact info
    edgar_user_agent: str = "FinanceMatrixAgent contact@example.com"

    # Transcripts
    transcripts_provider: str = "manual"  # manual | fmp | api_ninjas
    transcripts_api_key: str = ""

    # Storage
    database_url: str = "postgresql+psycopg://matrix:matrix@localhost:5432/matrix"

    # Guardrails
    daily_budget_usd: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
