"""Central configuration, loaded from environment variables / .env.

Kept deliberately simple (no secrets manager, no external config service) so
the whole pipeline can run for $0 inside GitHub Actions using repo secrets.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    default_timezone: str = "Africa/Johannesburg"

    database_url: str = "sqlite:///data/property_monitor.db"

    inbox_dir: Path = Path("data/inbox")
    raw_document_archive_dir: Path = Path("data/raw_documents")
    reports_dir: Path = Path("data/reports")
    max_upload_mb: int = 25

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "alerts@example.org"
    alert_email_to: str = ""

    alert_min_opportunity_score: int = 0
    always_send_digest: bool = False

    geocoding_enabled: bool = False
    geocoding_user_agent: str = "distressed-property-monitor"

    auction_soon_threshold_days: int = 7
    source_stale_threshold_days: int = 30

    scoring_version: str = "2026.1"

    # Comma-separated town/area names for the (non-scraping) weekly watch
    # reminder - see app/services/area_watch.py for why this doesn't fetch
    # anything automatically.
    watch_areas: str = "Potchefstroom,Fochville,Vereeniging"


settings = Settings()
