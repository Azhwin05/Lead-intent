"""
scoring/roas_scorer.py
───────────────────────
ROAS Risk Scoring Engine.

Each lead is scored 1-10 across five signals:

  Signal 1 — Creative Fatigue   (0-2)  days_running
  Signal 2 — Ad Volume          (0-2)  num_ads_running
  Signal 3 — Copy Quality       (0-2)  Gemini evaluation
  Signal 4 — Traffic Gap        (0-2)  paid_traffic_percentage
  Signal 5 — Business Size Risk (0-2)  company_employee_count

  Total: 0-10   |  HOT = 8-10  |  WARM = 5-7  |  COLD = 0-4

Gemini is called ONLY for Signal 3 (copy quality) to minimise
token spend. All other signals are deterministic rule-based.
"""

from __future__ import annotations

import json
import logging
import time
from typing import List, Optional

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from models.lead import Lead, LeadTier, ScoreBreakdown
from utils.logging_setup import get_logger
from utils.rate_limiter import gemini_limiter
from utils.retry import with_retry

logger = get_logger(__name__)

_limiter = gemini_limiter()

_COPY_QUALITY_PROMPT = """You are an expert Meta ads analyst. Evaluate the following ad copy snippet and rate it on a scale of 0-2 for QUALITY from an advertiser's perspective:

2 = POOR quality (generic, no clear offer, clichéd, no social proof)
1 = AVERAGE quality (some specificity but weak CTA or vague benefit)
0 = STRONG quality (specific offer, clear CTA, social proof, compelling)

Return ONLY a valid JSON object with exactly two keys:
{"score": <int 0|1|2>, "reason": "<one sentence explanation>"}

Ad copy to evaluate:

{ad_copy}"""


# ── Signal calculators ────────────────────────────────────────────────────────

def _score_creative_fatigue(days_running: int) -> int:
    """Signal 1: longer-running = more likely fatigued and under-performing."""
    if days_running >= 60:
        return 2
    if days_running >= 30:
        return 1
    return 0


def _score_ad_volume(num_ads: int) -> int:
    """Signal 2: many ads = desperate A/B testing = low confidence in creative."""
    if num_ads >= 10:
        return 2
    if num_ads >= 5:
        return 1
    return 0


def _score_traffic_gap(paid_pct: Optional[float]) -> int:
    """Signal 4: heavy reliance on paid traffic = fragile, expensive unit economics."""
    if paid_pct is None:
        return 1  # unknown — moderate risk assumed
    if paid_pct >= 60.0:
        return 2
    if paid_pct >= 30.0:
        return 1
    return 0


def _score_business_size(employee_count: Optional[int]) -> int:
    """Signal 5: small businesses rarely have in-house media buying expertise."""
    if employee_count is None:
        return 1  # unknown — moderate risk
    if employee_count <= 10:
        return 2
    if employee_count <= 50:
        return 1
    return 0


# ── Gemini Copy Quality Scorer ───────────────────────────────────────────────

@with_retry(max_attempts=3, min_wait=1.0, max_wait=10.0)
def _gemini_score_copy(
    ad_copy: str,
    model: genai.GenerativeModel,
) -> tuple[int, str]:
    """
    Use Gemini to rate the quality of ad copy.

    Returns
    -------
    (score: int 0-2, reason: str)
    """
    _limiter.acquire_sync()

    if not ad_copy or not ad_copy.strip():
        return 1, "No ad copy available — defaulting to average score."

    try:
        prompt = _COPY_QUALITY_PROMPT.format(ad_copy=ad_copy[:400])
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(
                temperature=0.1,
                max_output_tokens=100,
                response_mime_type="application/json",
            )
        )
        raw = response.text or "{}"
        parsed = json.loads(raw)
        score = int(parsed.get("score", 1))
        reason = str(parsed.get("reason", ""))
        return max(0, min(2, score)), reason

    except Exception as exc:
        # Catch rate limits and other API errors
        if "429" in str(exc) or "quota" in str(exc).lower():
            logger.warning("Gemini rate limit hit — backing off 60s")
            time.sleep(60)
            raise
        logger.warning("Failed to parse Gemini copy score: %s", exc)
        return 1, "Could not parse Gemini response — defaulting to average."


# ── Core scoring function ─────────────────────────────────────────────────────

def _score_lead(lead: Lead, model: genai.GenerativeModel) -> Lead:
    """Apply all five signals and populate scoring fields on the lead."""

    # Rule-based signals
    s1 = _score_creative_fatigue(lead.days_running)
    s2 = _score_ad_volume(lead.num_ads_running)
    s4 = _score_traffic_gap(lead.paid_traffic_percentage)
    s5 = _score_business_size(lead.company_employee_count)

    # Gemini signal
    try:
        s3, gemini_reason = _gemini_score_copy(lead.ad_copy_snippet or "", model)
    except Exception as exc:
        logger.error("Gemini copy scoring failed for '%s': %s — using default", lead.brand_name, exc)
        s3, gemini_reason = 1, "Gemini evaluation unavailable — defaulting to average."

    total = s1 + s2 + s3 + s4 + s5

    lead.score_breakdown = ScoreBreakdown(
        creative_fatigue=s1,
        ad_volume=s2,
        copy_quality=s3,
        traffic_gap=s4,
        business_size=s5,
    )
    lead.roas_risk_score = total
    lead.gpt_copy_analysis = gemini_reason

    if total >= 8:
        lead.lead_tier = LeadTier.HOT
    elif total >= 5:
        lead.lead_tier = LeadTier.WARM
    else:
        lead.lead_tier = LeadTier.COLD

    logger.debug(
        "Scored '%s': %d/10 [%s] s1=%d s2=%d s3=%d s4=%d s5=%d",
        lead.brand_name,
        total,
        lead.lead_tier.value,
        s1, s2, s3, s4, s5,
    )
    return lead


# ── Public API ────────────────────────────────────────────────────────────────

def score_leads(
    enriched_list: List[Lead],
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.0-flash-exp",
) -> List[Lead]:
    """
    Score all enriched leads for ROAS underperformance risk.

    Parameters
    ----------
    enriched_list: Leads after Apollo + Similarweb enrichment.
    api_key:       Gemini API key (falls back to settings if None).
    model_name:    Gemini model to use for copy quality scoring.

    Returns
    -------
    Leads with roas_risk_score, score_breakdown, lead_tier populated.
    Sorted descending by roas_risk_score.
    """
    if not api_key:
        from config.settings import get_settings
        api_key = get_settings().gemini_api_key

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    scored: List[Lead] = []
    failed = 0

    for lead in enriched_list:
        try:
            scored.append(_score_lead(lead, model))
        except Exception as exc:
            failed += 1
            logger.error("Scoring failed for '%s': %s", lead.brand_name, exc)
            # Still include the lead — just without scores
            lead.roas_risk_score = 0
            lead.lead_tier = LeadTier.COLD
            scored.append(lead)

    # Sort by score descending
    scored.sort(key=lambda l: l.roas_risk_score or 0, reverse=True)

    tier_counts = {
        LeadTier.HOT: sum(1 for l in scored if l.lead_tier == LeadTier.HOT),
        LeadTier.WARM: sum(1 for l in scored if l.lead_tier == LeadTier.WARM),
        LeadTier.COLD: sum(1 for l in scored if l.lead_tier == LeadTier.COLD),
    }
    logger.info(
        "Scoring complete: %d HOT | %d WARM | %d COLD | %d failed",
        tier_counts[LeadTier.HOT],
        tier_counts[LeadTier.WARM],
        tier_counts[LeadTier.COLD],
        failed,
    )
    return scored


def filter_hot_leads(scored_list: List[Lead], min_score: int = 7) -> List[Lead]:
    """
    Return only leads with roas_risk_score >= min_score.

    Parameters
    ----------
    scored_list: Output from score_leads().
    min_score:   Minimum score threshold (default 7 = WARM+).
    """
    hot = [l for l in scored_list if (l.roas_risk_score or 0) >= min_score]
    logger.info("Filtered to %d leads with score >= %d", len(hot), min_score)
    return hot
