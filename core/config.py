"""Configuration — charge .env via Pydantic Settings."""

from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Google Gemini ---
    google_gemini_api_key: str = ""

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # --- Search / Scraping ---
    serpapi_key: str = ""
    spider_api_key: str = ""
    firecrawl_api_key: str = ""
    apify_token: str = ""
    xai_api_key: str = ""

    # --- Claude OAuth ---
    claude_credentials_path: str = str(
        Path.home() / ".claude" / ".credentials.json"
    )
    claude_model: str = "claude-sonnet-4-5-20250929"

    # --- Gemini (embeddings only) ---
    gemini_embedding_model: str = "gemini-embedding-001"

    # --- OpenRouter (fast model, no restrictions) ---
    openrouter_api_key: str = ""
    openrouter_model: str = "qwen/qwen3-235b-a22b"
    openrouter_vision_model: str = "qwen/qwen2.5-vl-72b-instruct"

    # --- Dashboard ---
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8000


settings = Settings()
