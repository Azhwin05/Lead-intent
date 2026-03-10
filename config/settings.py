"""
config/settings.py
──────────────────
Centralised, type-safe configuration using pydantic-settings.

All values are read from environment variables (or a .env file).
Importing this module raises a clear error at startup if any
required variable is missing — fail fast, never silently.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings — sourced from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── API Keys ─────────────────────────────────────────────
    gemini_api_key: str
    apollo_api_key: str
    similarweb_api_key: Optional[str] = None   # optional — falls back to heuristics
    airtable_api_key: str
    airtable_base_id: str
    instantly_api_key: str
    instantly_campaign_id: str
    slack_webhook_url: str

    # ── Meta Ad Library ───────────────────────────────────────
    meta_access_token: str
    meta_app_id: str
    meta_app_secret: str

    # ── Pipeline Config ───────────────────────────────────────
    max_leads_per_run: int = 100
    min_days_running: int = 30
    min_score_threshold: int = 7
    hot_lead_alert_threshold: int = 9

    scrape_keywords: List[str] = [
        "skincare",
        "supplements",
        "fashion",
        "pet products",
        "home goods",
        "fitness",
        "beauty",
        "jewellery",
        "coffee",
        "candles",
        "apparel",
        "hair care",
        "vitamins",
        "wellness",
    ]

    schedule_hour: int = 6
    schedule_minute: int = 0

    # ── Agency Config (used in email generation) ──────────────
    agency_name: str = "Your Agency Name"
    agency_sender_name: str = "Your Name"
    agency_case_study_brand: str = "[INSERT CASE STUDY BRAND]"
    agency_case_study_result: str = "[INSERT RESULT e.g. 620% ROAS]"

    # ── Airtable Table Name ───────────────────────────────────
    airtable_table_name: str = "Leads"

    # ── Playwright ────────────────────────────────────────────
    playwright_headless: bool = True
    playwright_slow_mo: int = 0       # ms between actions — raise for debugging
    scraper_timeout_ms: int = 30_000  # page-level timeout

    # ── Validators ───────────────────────────────────────────

    @field_validator("scrape_keywords", mode="before")
    @classmethod
    def _parse_keywords(cls, v: object) -> List[str]:
        """Accept comma-separated string or list."""
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return v  # type: ignore[return-value]

    @field_validator("schedule_hour")
    @classmethod
    def _validate_hour(cls, v: int) -> int:
        if not 0 <= v <= 23:
            raise ValueError(f"schedule_hour must be 0-23, got {v}")
        return v

    @field_validator("schedule_minute")
    @classmethod
    def _validate_minute(cls, v: int) -> int:
        if not 0 <= v <= 59:
            raise ValueError(f"schedule_minute must be 0-59, got {v}")
        return v

    @model_validator(mode="after")
    def _check_required_keys(self) -> "Settings":
        """Raise a descriptive error for any blank required key."""
        required = {
            "gemini_api_key": self.gemini_api_key,
            "apollo_api_key": self.apollo_api_key,
            "airtable_api_key": self.airtable_api_key,
            "airtable_base_id": self.airtable_base_id,
            "instantly_api_key": self.instantly_api_key,
            "instantly_campaign_id": self.instantly_campaign_id,
            "slack_webhook_url": self.slack_webhook_url,
            "meta_access_token": self.meta_access_token,
            "meta_app_id": self.meta_app_id,
            "meta_app_secret": self.meta_app_secret,
        }
        missing = [k for k, v in required.items() if not v or v.startswith("your_")]
        if missing:
            raise ValueError(
                f"Missing or placeholder values for required settings: {missing}. "
                "Copy .env.example → .env and fill in real credentials."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.

    Uses lru_cache so the .env file is only parsed once per process.
    In tests, call ``get_settings.cache_clear()`` after patching env vars.
    """
    try:
        s = Settings()
        logger.debug("Settings loaded successfully.")
        return s
    except Exception as exc:
        logger.critical("Failed to load settings: %s", exc)
        raise


if __name__ == "__main__":
    import sys

    def _mask(value: str, show: int = 4) -> str:
        if not value or value.startswith("your_"):
            return "(not set)"
        return value[:show] + "****" if len(value) > show else "****"

    try:
        s = get_settings()
    except Exception as exc:
        print(f"ERROR loading settings: {exc}", file=sys.stderr)
        sys.exit(1)

    print("Settings loaded successfully.\n")
    print("── API Keys ─────────────────────────────────────────────")
    print(f"  gemini_api_key        : {_mask(s.gemini_api_key)}")
    print(f"  apollo_api_key        : {_mask(s.apollo_api_key)}")
    print(f"  similarweb_api_key    : {_mask(s.similarweb_api_key or '')}")
    print(f"  airtable_api_key      : {_mask(s.airtable_api_key)}")
    print(f"  airtable_base_id      : {_mask(s.airtable_base_id)}")
    print(f"  instantly_api_key     : {_mask(s.instantly_api_key)}")
    print(f"  instantly_campaign_id : {_mask(s.instantly_campaign_id)}")
    print(f"  slack_webhook_url     : {_mask(s.slack_webhook_url)}")
    print("── Meta Ad Library ──────────────────────────────────────")
    print(f"  meta_access_token     : {_mask(s.meta_access_token)}")
    print(f"  meta_app_id           : {_mask(s.meta_app_id)}")
    print(f"  meta_app_secret       : {_mask(s.meta_app_secret)}")
    print("── Pipeline Config ──────────────────────────────────────")
    print(f"  max_leads_per_run     : {s.max_leads_per_run}")
    print(f"  min_days_running      : {s.min_days_running}")
    print(f"  min_score_threshold   : {s.min_score_threshold}")
    print(f"  hot_lead_alert_thres  : {s.hot_lead_alert_threshold}")
    print(f"  schedule              : {s.schedule_hour:02d}:{s.schedule_minute:02d}")
    print("── Agency ───────────────────────────────────────────────")
    print(f"  agency_name           : {s.agency_name}")
    print(f"  agency_sender_name    : {s.agency_sender_name}")
