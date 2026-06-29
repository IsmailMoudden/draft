"""Application-wide configuration.

Environment variables are loaded from a .env file. All fields have safe
defaults so the system can run without a .env file (LLM and Teams calls
are no-ops when keys are empty).

TPT DATA SOURCES — TWO DISTINCT THINGS:
  tpt_snapshot_*  →  Daily Excel files (T and T-1) — position snapshots.
                     Already connected. Loaded by data_loaders/tpt_loader.py.
  tpt_api_*       →  Future REST API for transaction logs (NEW/AMEND/CANCEL).
                     Not yet connected. Will be loaded by a future 'fetch_logs'
                     node. The model (TptTradeLog) is already defined.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Azure OpenAI (LLM writer) ---
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_max_tokens: int = 400        # per desk comment
    azure_openai_temperature: float = 0.3    # low = factual, high = creative

    # --- Database (future SQL source for PnL attribution + comments) ---
    postgres_dsn: str = "postgresql://localhost/mo_intelligence"

    # --- Notifications ---
    teams_channel_webhook_url: str = ""      # Teams channel for generated comments

    # --- Pipeline settings ---
    pipeline_timezone: str = "Europe/London"
    log_level: str = "INFO"
    dry_run: bool = False                    # True = generate comments but don't post

    # --- TPT position snapshots (CURRENTLY CONNECTED) ---
    # Excel files provided daily. File naming convention: ST-<DESK>-PM-PNL Oil BBL T.xlsx
    # These are loaded directly in data_loaders/tpt_loader.py.
    # No credentials needed — files are provided via shared folder or SQL in future.
    tpt_snapshot_dir: str = ""              # directory to scan for T/T1 files (future)
    tpt_snapshot_pattern: str = "ST-*-PM-PNL Oil BBL T*.xlsx"

    # --- TPT trade log API (NOT YET CONNECTED — future) ---
    # REST API that returns transaction-level events (NEW/AMEND/CANCEL trades).
    # Different from snapshots: logs explain the TRADES attribution bucket.
    # Will be consumed by a future 'fetch_logs' node in orchestrator/graph.py.
    tpt_api_base_url: str = ""              # e.g. "https://tpt.internal/api/v1"
    tpt_api_key: str = ""
    tpt_api_lookback_days: int = 1          # how many days of logs to fetch


settings = Settings()

__all__ = ["Settings", "settings"]
