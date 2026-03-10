"""
models/lead.py
──────────────
Pydantic v2 data models for the entire lead generation pipeline.

These models serve as the single source of truth for the data schema
and are used by all modules for validation, serialisation, and typing.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_serializer


# ── Enums ─────────────────────────────────────────────────────────────────────

class LeadTier(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class AdCreativeType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    UNKNOWN = "unknown"


class OutreachStatus(str, Enum):
    PENDING = "Pending"
    SENT = "Sent"
    REPLIED = "Replied"
    BOOKED = "Booked"


# ── Sub-models ────────────────────────────────────────────────────────────────

class ScoreBreakdown(BaseModel):
    """Per-signal scores that sum to the total ROAS risk score."""

    creative_fatigue: int = Field(0, ge=0, le=2, description="Signal 1 — days running")
    ad_volume: int = Field(0, ge=0, le=2, description="Signal 2 — num ads")
    copy_quality: int = Field(0, ge=0, le=2, description="Signal 3 — GPT copy eval")
    traffic_gap: int = Field(0, ge=0, le=2, description="Signal 4 — paid traffic %")
    business_size: int = Field(0, ge=0, le=2, description="Signal 5 — employee count")

    @property
    def total(self) -> int:
        return (
            self.creative_fatigue
            + self.ad_volume
            + self.copy_quality
            + self.traffic_gap
            + self.business_size
        )


class EmailMessage(BaseModel):
    """A single email (subject + body)."""

    subject: str = Field(..., max_length=200)
    body: str = Field(..., max_length=2000)


class OutreachSequence(BaseModel):
    """Three-email cold outreach sequence."""

    email_1: EmailMessage  # Day 1  — The Observation
    email_2: EmailMessage  # Day 4  — The Proof
    email_3: EmailMessage  # Day 9  — The Soft Close


# ── Core Lead Model ───────────────────────────────────────────────────────────

class Lead(BaseModel):
    """
    Canonical data model for a single eCommerce lead.

    Fields are populated incrementally as the lead moves through pipeline stages:
    Scrape → Enrich → Score → Outreach → Storage
    """

    # ── Scraper fields ──────────────────────────────────────────
    brand_name: str = Field(..., description="Facebook page / brand name")
    page_url: Optional[str] = Field(None, description="Facebook page URL")
    website_url: Optional[str] = Field(None, description="Brand website URL")
    ad_id: Optional[str] = Field(None, description="Meta ad ID")
    ad_start_date: Optional[str] = Field(None, description="Date ad started running")
    days_running: int = Field(0, ge=0, description="Days since ad started")
    ad_creative_type: AdCreativeType = AdCreativeType.UNKNOWN
    ad_copy_snippet: Optional[str] = Field(None, max_length=500, description="First ~200 chars of ad copy")
    num_ads_running: int = Field(0, ge=0, description="Total active ads for this page")

    # ── Apollo enrichment fields ─────────────────────────────────
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    contact_linkedin: Optional[str] = None
    company_employee_count: Optional[int] = Field(None, ge=0)
    company_industry: Optional[str] = None

    # ── Similarweb enrichment fields ─────────────────────────────
    monthly_visits: Optional[int] = Field(None, ge=0)
    paid_traffic_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    bounce_rate: Optional[float] = Field(None, ge=0.0, le=100.0)

    # ── Scoring fields ───────────────────────────────────────────
    roas_risk_score: Optional[int] = Field(None, ge=0, le=10)
    score_breakdown: Optional[ScoreBreakdown] = None
    gpt_copy_analysis: Optional[str] = None
    lead_tier: Optional[LeadTier] = None

    # ── Outreach fields ──────────────────────────────────────────
    outreach: Optional[OutreachSequence] = None

    # ── Metadata ─────────────────────────────────────────────────
    date_added: Optional[date] = Field(default_factory=date.today)
    airtable_record_id: Optional[str] = None
    outreach_status: OutreachStatus = OutreachStatus.PENDING
    notes: Optional[str] = None

    # ── Validators ───────────────────────────────────────────────

    @field_validator("website_url", "page_url", mode="before")
    @classmethod
    def _clean_url(cls, v: Optional[str]) -> Optional[str]:
        """Normalise empty strings to None."""
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

    @field_validator("contact_email", mode="before")
    @classmethod
    def _clean_email(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            v = v.strip().lower()
            return v if "@" in v else None
        return v

    # ── Helpers ──────────────────────────────────────────────────

    @property
    def domain(self) -> Optional[str]:
        """Extract bare domain from website_url."""
        if not self.website_url:
            return None
        url = self.website_url
        for prefix in ("https://", "http://", "www."):
            url = url.replace(prefix, "")
        return url.split("/")[0].lower()

    @property
    def first_name(self) -> str:
        if self.contact_name:
            return self.contact_name.split()[0]
        return "there"

    def to_airtable_fields(self) -> Dict[str, Any]:
        """Serialise lead to Airtable field names."""
        fields: Dict[str, Any] = {
            "Brand Name": self.brand_name,
            "Website": self.website_url or "",
            "Ad Platform": "Meta",
            "Days Running": self.days_running,
            "Num Ads": self.num_ads_running,
        }
        if self.monthly_visits is not None:
            fields["Monthly Traffic"] = self.monthly_visits
        if self.paid_traffic_percentage is not None:
            fields["Paid Traffic Pct"] = self.paid_traffic_percentage
        if self.roas_risk_score is not None:
            fields["ROAS Risk Score"] = self.roas_risk_score
        if self.lead_tier:
            fields["Lead Tier"] = self.lead_tier.value
        if self.score_breakdown:
            import json
            fields["Score Breakdown"] = json.dumps(self.score_breakdown.model_dump())
        if self.contact_name:
            fields["Contact Name"] = self.contact_name
        if self.contact_title:
            fields["Contact Title"] = self.contact_title
        if self.contact_email:
            fields["Contact Email"] = self.contact_email
        if self.contact_linkedin:
            fields["Contact LinkedIn"] = self.contact_linkedin
        if self.outreach:
            fields["Email 1 Subject"] = self.outreach.email_1.subject
            fields["Email 1 Body"] = self.outreach.email_1.body
            fields["Email 2 Subject"] = self.outreach.email_2.subject
            fields["Email 2 Body"] = self.outreach.email_2.body
            fields["Email 3 Subject"] = self.outreach.email_3.subject
            fields["Email 3 Body"] = self.outreach.email_3.body
        fields["Outreach Status"] = self.outreach_status.value
        if self.date_added:
            fields["Date Added"] = self.date_added.isoformat()
        if self.notes:
            fields["Notes"] = self.notes
        return fields


# ── Pipeline Stats Model ──────────────────────────────────────────────────────

class PipelineStats(BaseModel):
    """Collects run-level statistics for Slack summary."""

    run_date: date = Field(default_factory=date.today)
    scraped: int = 0
    enriched: int = 0
    scored: int = 0
    hot_leads: int = 0
    emails_generated: int = 0
    airtable_created: int = 0
    airtable_updated: int = 0
    airtable_failed: int = 0
    outreach_sent: int = 0
    outreach_failed: int = 0
    outreach_skipped: int = 0
    errors: List[str] = Field(default_factory=list)

    def record_error(self, step: str, message: str) -> None:
        self.errors.append(f"[{step}] {message}")
