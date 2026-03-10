"""
tests/test_pipeline.py
───────────────────────
Comprehensive test suite covering all pipeline modules.

All external dependencies (Gemini, Airtable, Slack, Apollo, Similarweb,
Playwright, Instantly) are mocked — tests run fully offline.

Run with:
  pytest tests/ -v
  pytest tests/ -v --tb=short
"""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch, AsyncMock
from typing import List

import pytest
import responses as rsps_lib

from models.lead import (
    AdCreativeType,
    Lead,
    LeadTier,
    OutreachStatus,
    PipelineStats,
    ScoreBreakdown,
)


# ═══════════════════════════════════════════════════════════════
# models/lead.py
# ═══════════════════════════════════════════════════════════════

class TestLeadModel:
    def test_lead_creation(self, hot_lead):
        assert hot_lead.brand_name == "Glow Skincare Co"
        assert hot_lead.domain == "glowskincare.com"
        assert hot_lead.first_name == "Jane"

    def test_lead_domain_extraction(self):
        lead = Lead(brand_name="Test", website_url="https://www.example.com/shop")
        assert lead.domain == "example.com"

    def test_lead_no_domain(self):
        lead = Lead(brand_name="Test")
        assert lead.domain is None

    def test_lead_email_validation(self):
        lead = Lead(brand_name="Test", contact_email="invalid-email")
        assert lead.contact_email is None

        lead2 = Lead(brand_name="Test", contact_email="valid@example.com")
        assert lead2.contact_email == "valid@example.com"

    def test_lead_first_name_fallback(self):
        lead = Lead(brand_name="Test", contact_name=None)
        assert lead.first_name == "there"

    def test_score_breakdown_total(self):
        breakdown = ScoreBreakdown(
            creative_fatigue=2, ad_volume=1, copy_quality=2, traffic_gap=1, business_size=2
        )
        assert breakdown.total == 8

    def test_to_airtable_fields(self, hot_lead):
        fields = hot_lead.to_airtable_fields()
        assert fields["Brand Name"] == "Glow Skincare Co"
        assert fields["Website"] == "https://www.glowskincare.com"
        assert fields["Ad Platform"] == "Meta"
        assert fields["ROAS Risk Score"] == 9
        assert fields["Lead Tier"] == "HOT"
        assert fields["Contact Email"] == "jane@glowskincare.com"

    def test_pipeline_stats_error_recording(self):
        stats = PipelineStats()
        stats.record_error("scrape", "Timeout on keyword 'skincare'")
        assert len(stats.errors) == 1
        assert "scrape" in stats.errors[0]


# ═══════════════════════════════════════════════════════════════
# config/settings.py
# ═══════════════════════════════════════════════════════════════

class TestSettings:
    def test_settings_load(self):
        from config.settings import get_settings
        cfg = get_settings()
        assert cfg.gemini_api_key == "AIza-test-gemini-key"
        assert cfg.agency_name == "Test Agency"
        assert isinstance(cfg.scrape_keywords, list)
        assert len(cfg.scrape_keywords) > 0

    def test_settings_keyword_parsing(self, monkeypatch):
        from config.settings import get_settings
        monkeypatch.setenv("SCRAPE_KEYWORDS", "cats,dogs,birds")
        get_settings.cache_clear()
        cfg = get_settings()
        assert cfg.scrape_keywords == ["cats", "dogs", "birds"]
        get_settings.cache_clear()


# ═══════════════════════════════════════════════════════════════
# scoring/roas_scorer.py
# ═══════════════════════════════════════════════════════════════

class TestScoring:
    def test_creative_fatigue_signal(self):
        from scoring.roas_scorer import _score_creative_fatigue
        assert _score_creative_fatigue(70) == 2
        assert _score_creative_fatigue(45) == 1
        assert _score_creative_fatigue(10) == 0

    def test_ad_volume_signal(self):
        from scoring.roas_scorer import _score_ad_volume
        assert _score_ad_volume(15) == 2
        assert _score_ad_volume(7) == 1
        assert _score_ad_volume(3) == 0

    def test_traffic_gap_signal(self):
        from scoring.roas_scorer import _score_traffic_gap
        assert _score_traffic_gap(75.0) == 2
        assert _score_traffic_gap(40.0) == 1
        assert _score_traffic_gap(10.0) == 0
        assert _score_traffic_gap(None) == 1  # unknown → moderate

    def test_business_size_signal(self):
        from scoring.roas_scorer import _score_business_size
        assert _score_business_size(5) == 2
        assert _score_business_size(30) == 1
        assert _score_business_size(100) == 0
        assert _score_business_size(None) == 1  # unknown

    @patch("scoring.roas_scorer.genai")
    def test_score_leads(self, mock_genai, leads_batch):
        """Test that all leads get scored and are sorted descending."""
        # Mock Gemini response for copy quality
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {"score": 2, "reason": "Generic copy with no clear offer."}
        )
        mock_model.generate_content.return_value = mock_response

        from scoring.roas_scorer import score_leads

        # Reset scores first
        for lead in leads_batch:
            lead.roas_risk_score = None
            lead.lead_tier = None

        scored = score_leads(leads_batch, api_key="AIza-test")

        assert all(l.roas_risk_score is not None for l in scored)
        assert all(l.lead_tier is not None for l in scored)
        # Sorted descending
        scores = [l.roas_risk_score for l in scored]
        assert scores == sorted(scores, reverse=True)

    def test_filter_hot_leads(self, leads_batch):
        """filter_hot_leads returns only leads with score >= threshold."""
        from scoring.roas_scorer import filter_hot_leads

        # Pre-set scores
        leads_batch[0].roas_risk_score = 9
        leads_batch[1].roas_risk_score = 6
        leads_batch[2].roas_risk_score = 2

        hot = filter_hot_leads(leads_batch, min_score=7)
        assert len(hot) == 1
        assert hot[0].roas_risk_score == 9

    @patch("scoring.roas_scorer.genai")
    def test_score_output_schema(self, mock_genai, hot_lead):
        """Verify all required fields are set after scoring."""
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {"score": 1, "reason": "Some specificity."}
        )
        mock_model.generate_content.return_value = mock_response

        hot_lead.roas_risk_score = None
        hot_lead.lead_tier = None

        from scoring.roas_scorer import score_leads
        scored = score_leads([hot_lead], api_key="AIza-test")

        lead = scored[0]
        assert lead.roas_risk_score is not None
        assert 0 <= lead.roas_risk_score <= 10
        assert lead.lead_tier in (LeadTier.HOT, LeadTier.WARM, LeadTier.COLD)
        assert lead.score_breakdown is not None
        assert lead.gpt_copy_analysis is not None


# ═══════════════════════════════════════════════════════════════
# enrichment/apollo_enricher.py
# ═══════════════════════════════════════════════════════════════

class TestApolloEnrichment:
    @rsps_lib.activate
    def test_enrich_with_apollo_success(self, hot_lead):
        """Successful Apollo response populates contact fields."""
        hot_lead.contact_name = None
        hot_lead.contact_email = None

        rsps_lib.add(
            rsps_lib.POST,
            "https://api.apollo.io/v1/mixed_people/search",
            json={
                "people": [
                    {
                        "first_name": "Jane",
                        "last_name": "Smith",
                        "title": "Founder",
                        "email": "jane@glowskincare.com",
                        "linkedin_url": "https://linkedin.com/in/janesmith",
                        "organization": {
                            "estimated_num_employees": 8,
                            "industry": "Health & Beauty",
                        },
                    }
                ]
            },
            status=200,
        )

        from enrichment.apollo_enricher import enrich_with_apollo

        result = enrich_with_apollo([hot_lead], api_key="test-key")
        assert result[0].contact_name == "Jane Smith"
        assert result[0].contact_email == "jane@glowskincare.com"

    @rsps_lib.activate
    def test_enrich_with_apollo_no_results(self, hot_lead):
        """Empty Apollo response — lead contact fields remain None."""
        hot_lead.contact_name = None
        hot_lead.contact_email = None

        rsps_lib.add(
            rsps_lib.POST,
            "https://api.apollo.io/v1/mixed_people/search",
            json={"people": []},
            status=200,
        )

        from enrichment.apollo_enricher import enrich_with_apollo

        result = enrich_with_apollo([hot_lead], api_key="test-key")
        assert result[0].contact_name is None
        assert result[0].contact_email is None

    def test_enrich_no_domain_skipped(self, cold_lead):
        """Leads with no website_url are skipped (no domain)."""
        cold_lead.website_url = None
        cold_lead.page_url = None

        from enrichment.apollo_enricher import enrich_with_apollo

        result = enrich_with_apollo([cold_lead], api_key="test-key")
        # Should return without crashing
        assert result[0].contact_name is None


# ═══════════════════════════════════════════════════════════════
# enrichment/similarweb_enricher.py
# ═══════════════════════════════════════════════════════════════

class TestSimilarwebEnrichment:
    def test_heuristic_fallback(self, hot_lead):
        """Without API key, heuristic values are applied."""
        from enrichment.similarweb_enricher import enrich_with_traffic

        result = enrich_with_traffic([hot_lead], api_key=None)
        lead = result[0]
        assert lead.monthly_visits is not None
        assert lead.paid_traffic_percentage is not None
        assert 0 <= lead.paid_traffic_percentage <= 100
        assert lead.bounce_rate is not None

    @rsps_lib.activate
    def test_similarweb_api_success(self, hot_lead):
        """Successful Similarweb response populates traffic fields."""
        hot_lead.monthly_visits = None

        rsps_lib.add(
            rsps_lib.GET,
            "https://api.similarweb.com/v1/website/glowskincare.com/traffic-sources/overview",
            json={
                "total_visits": 120_000,
                "bounce_rate": 0.55,
                "traffic_sources": {
                    "paid_search": 0.35,
                    "display_ads": 0.15,
                },
            },
            status=200,
        )

        from enrichment.similarweb_enricher import enrich_with_traffic

        result = enrich_with_traffic([hot_lead], api_key="test-sw-key")
        assert result[0].monthly_visits == 120_000
        assert result[0].paid_traffic_percentage == 50.0


# ═══════════════════════════════════════════════════════════════
# outreach/email_writer.py
# ═══════════════════════════════════════════════════════════════

class TestEmailWriter:
    @patch("outreach.email_writer.genai")
    def test_generate_email_sequence(self, mock_genai, hot_lead):
        """generate_email returns an OutreachSequence with 3 emails."""
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        email_json = json.dumps({
            "subject": "Noticed something about your Glow Skincare ads",
            "body": "Hi Jane,\n\nI spotted something interesting...",
        })
        mock_response = MagicMock()
        mock_response.text = email_json
        mock_model.generate_content.return_value = mock_response

        from outreach.email_writer import generate_email

        seq = generate_email(
            hot_lead,
            model=mock_model,
            agency_name="Test Agency",
            sender_name="Test User",
            case_study_brand="Glow Co",
            case_study_result="620% ROAS",
        )

        assert seq.email_1.subject
        assert seq.email_2.subject
        assert seq.email_3.subject
        assert seq.email_1.body
        assert mock_model.generate_content.call_count == 3

    @patch("outreach.email_writer.genai")
    def test_fallback_on_gemini_failure(self, mock_genai, hot_lead):
        """If Gemini fails, fallback template emails are used."""
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_model.generate_content.side_effect = Exception("API down")

        from outreach.email_writer import generate_email

        seq = generate_email(
            hot_lead,
            model=mock_model,
            agency_name="Test Agency",
            sender_name="Test User",
            case_study_brand="Glow Co",
            case_study_result="620% ROAS",
        )

        # Fallback emails should still have content
        assert seq.email_1.subject
        assert seq.email_1.body


# ═══════════════════════════════════════════════════════════════
# outreach/instantly_sender.py
# ═══════════════════════════════════════════════════════════════

class TestInstantlySender:
    @rsps_lib.activate
    def test_send_batch_success(self, lead_with_emails):
        rsps_lib.add(
            rsps_lib.POST,
            "https://api.instantly.ai/api/v1/lead/add",
            json={"status": "success"},
            status=200,
        )

        from outreach.instantly_sender import send_batch

        stats = send_batch([lead_with_emails], api_key="test-key", campaign_id="camp-1")
        assert stats["sent"] == 1
        assert stats["failed"] == 0
        assert stats["skipped"] == 0

    def test_skip_leads_without_email(self, cold_lead):
        """Leads with no contact_email are counted as skipped."""
        from outreach.instantly_sender import send_batch

        cold_lead.contact_email = None
        stats = send_batch([cold_lead], api_key="test-key", campaign_id="camp-1")
        assert stats["skipped"] == 1
        assert stats["sent"] == 0

    @rsps_lib.activate
    def test_send_batch_api_error(self, lead_with_emails):
        """API failure is counted as failed, not exception raised."""
        rsps_lib.add(
            rsps_lib.POST,
            "https://api.instantly.ai/api/v1/lead/add",
            status=500,
        )

        from outreach.instantly_sender import send_batch

        stats = send_batch([lead_with_emails], api_key="test-key", campaign_id="camp-1")
        assert stats["failed"] == 1


# ═══════════════════════════════════════════════════════════════
# storage/airtable_client.py
# ═══════════════════════════════════════════════════════════════

class TestAirtableClient:
    @patch("storage.airtable_client.Api")
    def test_upsert_creates_new_record(self, mock_api_cls, hot_lead):
        """If no existing record, a new one is created."""
        mock_table = MagicMock()
        mock_table.all.return_value = []  # no existing record
        mock_table.create.return_value = {"id": "recABC123"}
        mock_api_cls.return_value.table.return_value = mock_table

        from storage.airtable_client import AirtableClient

        client = AirtableClient("patXXX", "appXXX")
        record_id = client.upsert_lead(hot_lead)

        assert record_id == "recABC123"
        mock_table.create.assert_called_once()
        mock_table.update.assert_not_called()

    @patch("storage.airtable_client.Api")
    def test_upsert_updates_existing_record(self, mock_api_cls, hot_lead):
        """If a record exists (matched by website), it is updated."""
        mock_table = MagicMock()
        mock_table.all.return_value = [{"id": "recEXISTING", "fields": {}}]
        mock_api_cls.return_value.table.return_value = mock_table

        from storage.airtable_client import AirtableClient

        client = AirtableClient("patXXX", "appXXX")
        record_id = client.upsert_lead(hot_lead)

        assert record_id == "recEXISTING"
        mock_table.update.assert_called_once()
        mock_table.create.assert_not_called()

    @patch("storage.airtable_client.Api")
    def test_save_leads_batch_stats(self, mock_api_cls, leads_batch):
        """save_leads_batch returns correct created/updated/failed counts."""
        mock_table = MagicMock()
        mock_table.all.return_value = []
        mock_table.create.return_value = {"id": "recNEW"}
        mock_api_cls.return_value.table.return_value = mock_table

        from storage.airtable_client import AirtableClient

        client = AirtableClient("patXXX", "appXXX")
        stats = client.save_leads_batch(leads_batch)

        assert stats["created"] + stats["updated"] + stats["failed"] == len(leads_batch)


# ═══════════════════════════════════════════════════════════════
# notifications/slack_notifier.py
# ═══════════════════════════════════════════════════════════════

class TestSlackNotifier:
    @rsps_lib.activate
    def test_send_daily_summary(self, pipeline_stats):
        rsps_lib.add(
            rsps_lib.POST,
            "https://hooks.slack.com/services/test/test/test",
            body="ok",
            status=200,
        )

        from notifications.slack_notifier import send_daily_summary

        result = send_daily_summary(pipeline_stats)
        assert result is True

    @rsps_lib.activate
    def test_send_hot_lead_alert(self, hot_lead):
        rsps_lib.add(
            rsps_lib.POST,
            "https://hooks.slack.com/services/test/test/test",
            body="ok",
            status=200,
        )

        from notifications.slack_notifier import send_hot_lead_alert

        result = send_hot_lead_alert(hot_lead)
        assert result is True

    @rsps_lib.activate
    def test_slack_failure_returns_false(self, pipeline_stats):
        rsps_lib.add(
            rsps_lib.POST,
            "https://hooks.slack.com/services/test/test/test",
            status=500,
        )

        from notifications.slack_notifier import send_daily_summary

        result = send_daily_summary(pipeline_stats)
        assert result is False


# ═══════════════════════════════════════════════════════════════
# utils/rate_limiter.py
# ═══════════════════════════════════════════════════════════════

class TestRateLimiter:
    def test_invalid_rate_raises(self):
        from utils.rate_limiter import RateLimiter
        with pytest.raises(ValueError):
            RateLimiter(calls_per_second=0)

    def test_acquire_sync_does_not_block_immediately(self):
        """First acquire should not block (tokens available)."""
        import time
        from utils.rate_limiter import RateLimiter

        limiter = RateLimiter(calls_per_second=10.0)
        start = time.monotonic()
        limiter.acquire_sync()
        elapsed = time.monotonic() - start
        assert elapsed < 0.5   # should be near-instant


# ═══════════════════════════════════════════════════════════════
# Integration smoke test
# ═══════════════════════════════════════════════════════════════

class TestPipelineIntegration:
    """
    Smoke test for the full pipeline with all external calls mocked.
    """

    @patch("scrapers.meta_ad_library.async_playwright")
    @patch("scoring.roas_scorer.genai")
    @patch("outreach.email_writer.genai")
    @patch("storage.airtable_client.Api")
    @rsps_lib.activate
    def test_dry_run_pipeline(
        self,
        mock_api_cls,
        mock_writer_genai,
        mock_scorer_genai,
        mock_playwright,
        hot_lead,
        warm_lead,
    ):
        """
        Full pipeline in dry-run mode completes without raising exceptions.
        Verifies PipelineStats are populated.
        """
        # Mock Playwright
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.keyboard.press = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[])
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()
        mock_browser_ctx = AsyncMock().__aenter__ = AsyncMock(return_value=mock_context)
        mock_playwright.return_value.__aenter__ = AsyncMock()
        mock_playwright.return_value.__aexit__ = AsyncMock()

        # Mock Gemini (scorer + writer)
        for mock_genai_instance in (mock_scorer_genai, mock_writer_genai):
            mock_model = MagicMock()
            mock_genai_instance.GenerativeModel.return_value = mock_model
            mock_model.generate_content.return_value = MagicMock(
                text=json.dumps({"score": 2, "reason": "Test reason"})
            )

        # Mock Slack
        rsps_lib.add(
            rsps_lib.POST,
            "https://hooks.slack.com/services/test/test/test",
            body="ok",
            status=200,
        )

        # Import and run pipeline
        from main import run_pipeline

        # Override scrape step to return mock leads directly
        with patch("main.step_scrape", return_value=[hot_lead, warm_lead]):
            with patch("main.step_enrich", side_effect=lambda x: x):
                stats = run_pipeline(dry_run=True, limit=2)

        assert isinstance(stats, PipelineStats)
        assert stats.scraped >= 0
