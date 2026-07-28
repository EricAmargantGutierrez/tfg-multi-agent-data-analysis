from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.paths import PROJECT_ROOT


class Settings(BaseSettings):
    """
    Global configuration. Values come from (in order of precedence):
    env vars > .env file > defaults below.
    """

    project_name: str = "Multi-Agent Conversational Data Analysis"
    version: str = "0.1.0"

    # Which entry in src.llm.registry.MODELS to use when no model_key is
    # explicitly passed to build_llm().
    default_model: str = Field(default="groq")

    database_path: Path = PROJECT_ROOT / "data" / "superstore.db"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
