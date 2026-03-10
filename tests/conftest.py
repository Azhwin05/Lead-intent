"""
tests/conftest.py
──────────────────
Shared pytest fixtures for the ecom-lead-gen test suite.

All external API calls are mocked — tests run fully offline.
"""

from __future__ import annotations

import os
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from models.lead import (
    AdCreativeType,
    EmailMessage,
    Lead,
    LeadTier,
    OutreachSequence,
    OutreachStatus,
    PipelineStats,
    ScoreBreakdown,
)


# ── Environment fixtures ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """
    Inject fake credentials into the environment for every test.
    This prevents tests from requiring a real .env file.
    """
    env_vars = {
        "GEMINI_API_KEY": "AIza-test-gemini-key",
        "APOLLO_API_KEY": "test-apollo-key",
        "SIMILARWEB_API_KEY": "test-sw-key",
        "AIRTABLE_API_KEY": "patXXXXXXXXXXXXXX",
        "AIRTABLE_BASE_ID": "appXXXXXXXXXXXXXX",
        "INSTANTLY_API_KEY": "test-instantly-key",
        "INSTANTLY_CAMPAIGN_ID": "campaign-123",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/test/test/test",
        "AGENCY_NAME": "Test Agency",
        "AGENCY_SENDER_NAME": "Test User",
    }
    for key, val in env_vars.items():
        monkeypatch.setenv(key, val)

    # Clear lru_cache so Settings() re-reads the mocked env
    from config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── Sample lead fixtures ──────────────────────────────────────────────────────

def _make_lead(**overrides) -> Lead:
    defaults = {
        "brand_name": "Glow Skincare Co",
        "page_url": "https://www.facebook.com/GlowSkincare",
        "website_url": "https://www.glowskincare.com",
        "ad_id": "ad_001",
        "ad_start_date": "January 15, 2024",
        "days_running": 65,
        "ad_creative_type": AdCreativeType.IMAGE,
        "ad_copy_snippet": "Tired of dull skin? Try our Vitamin C serum! Shop now.",
        "num_ads_running": 12,
        "contact_name": "Jane Smith",
        "contact_title": "Founder",
        "contact_email": "jane@glowskincare.com",
        "contact_linkedin": "https://linkedin.com/in/janesmith",
        "company_employee_count": 8,
        "company_industry": "Health & Beauty",
        "monthly_visits": 45_000,
        "paid_traffic_percentage": 72.5,
        "bounce_rate": 58.0,
    }
    defaults.update(overrides)
    return Lead(**defaults)


@pytest.fixture
def hot_lead() -> Lead:
    """A pre-scored HOT lead (score = 9)."""
    lead = _make_lead()
    lead.roas_risk_score = 9
    lead.lead_tier = LeadTier.HOT
    lead.gpt_copy_analysis = "Generic copy with no clear offer or social proof."
    lead.score_breakdown = ScoreBreakdown(
        creative_fatigue=2,
        ad_volume=2,
        copy_quality=2,
        traffic_gap=2,
        business_size=2,
    )
    return lead


@pytest.fixture
def warm_lead() -> Lead:
    """A pre-scored WARM lead (score = 6)."""
    lead = _make_lead(
        brand_name="FitLife Supplements",
        website_url="https://www.fitlife.com",
        contact_email="ceo@fitlife.com",
        days_running=35,
        num_ads_running=6,
        paid_traffic_percentage=45.0,
        company_employee_count=25,
    )
    lead.roas_risk_score = 6
    lead.lead_tier = LeadTier.WARM
    lead.score_breakdown = ScoreBreakdown(
        creative_fatigue=1,
        ad_volume=1,
        copy_quality=2,
        traffic_gap=1,
        business_size=1,
    )
    return lead


@pytest.fixture
def cold_lead() -> Lead:
    """A pre-scored COLD lead (score = 2)."""
    lead = _make_lead(
        brand_name="Nike",
        website_url="https://www.nike.com",
        contact_email=None,
        days_running=45,
        num_ads_running=2,
        paid_traffic_percentage=15.0,
        company_employee_count=500,
    )
    lead.roas_risk_score = 2
    lead.lead_tier = LeadTier.COLD
    lead.score_breakdown = ScoreBreakdown(
        creative_fatigue=1,
        ad_volume=0,
        copy_quality=1,
        traffic_gap=0,
        business_size=0,
    )
    return lead


@pytest.fixture
def leads_batch(hot_lead, warm_lead, cold_lead) -> list[Lead]:
    return [hot_lead, warm_lead, cold_lead]


@pytest.fixture
def lead_with_emails(hot_lead) -> Lead:
    """HOT lead with a generated outreach sequence."""
    hot_lead.outreach = OutreachSequence(
        email_1=EmailMessage(
            subject="Noticed something about your ads",
            body="Hi Jane,\n\nI spotted your Glow Skincare ads — been running for 65 days...",
        ),
        email_2=EmailMessage(
            subject="What we did for a similar brand",
            body="Hi Jane,\n\nWanted to share a result from a similar skincare brand...",
        ),
        email_3=EmailMessage(
            subject="Last note from me",
            body="Hi Jane,\n\nClosing the loop...",
        ),
    )
    return hot_lead


@pytest.fixture
def pipeline_stats() -> PipelineStats:
    return PipelineStats(
        scraped=50,
        enriched=30,
        scored=50,
        hot_leads=8,
        emails_generated=8,
        airtable_created=6,
        airtable_updated=2,
        outreach_sent=7,
        outreach_skipped=1,
    )
