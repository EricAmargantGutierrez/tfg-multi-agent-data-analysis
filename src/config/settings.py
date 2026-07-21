from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.paths import PROJECT_ROOT


class Settings(BaseSettings):
    """
    Global configuration for the application.

    Values can come from:
    1. Default values defined below.
    2. The .env file.
    3. Environment variables.
    """

    # ------------------------------------------------------------------
    # Project
    # ------------------------------------------------------------------

    project_name: str = "Multi-Agent Conversational Data Analysis"
    version: str = "0.1.0"

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    llm_provider: str = Field(default="openai")
    llm_model: str = Field(default="gpt-4o-mini")

    openai_api_key: str | None = None
    groq_api_key: str | None = None

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    database_path: Path = PROJECT_ROOT / "data" / "superstore.db"

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()