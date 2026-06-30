"""App config — loaded from .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_max_tokens: int = 400
    azure_openai_temperature: float = 0.3

    # Database (future)
    postgres_dsn: str = "postgresql://localhost/mo_intelligence"

    # Teams notifications
    teams_channel_webhook_url: str = ""

    # Pipeline
    pipeline_timezone: str = "Europe/London"
    log_level: str = "INFO"
    dry_run: bool = False

    # TPT snapshot files (loaded directly as Excel)
    tpt_snapshot_dir: str = ""
    tpt_snapshot_pattern: str = "ST-*-PM-PNL Oil BBL T*.xlsx"

    # TPT trade log API (not yet connected)
    tpt_api_base_url: str = ""
    tpt_api_key: str = ""
    tpt_api_lookback_days: int = 1


settings = Settings()

__all__ = ["Settings", "settings"]
