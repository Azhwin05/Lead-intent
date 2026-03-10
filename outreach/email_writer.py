"""
outreach/email_writer.py
─────────────────────────
Gemini powered cold email generator.

Produces a personalised 3-email sequence for each HOT lead:
  Email 1 (Day 1) — The Observation   : specific insight about their ads
  Email 2 (Day 4) — The Proof         : relevant case study
  Email 3 (Day 9) — The Soft Close    : low-pressure follow-up

Emails are conversational, human, and brand-specific — never generic.
"""

from __future__ import annotations

import json
import logging
import time
from typing import List, Optional

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from models.lead import EmailMessage, Lead, OutreachSequence
from utils.logging_setup import get_logger
from utils.rate_limiter import gemini_limiter
from utils.retry import with_retry

logger = get_logger(__name__)

_limiter = gemini_limiter()

_SYSTEM_INSTRUCTION = """You are an expert cold email copywriter for a performance marketing agency that helps eCommerce brands dramatically improve their Meta ads ROAS.

Write emails that are:
• Conversational and warm — like a human reaching out, not a pitch
• Specific to this brand — reference real details from their ads
• Not salesy — lead with insight, not a hard sell
• Concise — respect the recipient's time
• No buzzwords, no corporate speak, no exclamation marks

Return ONLY a valid JSON object with the exact schema requested."""


# ── Email prompt builders ─────────────────────────────────────────────────────

def _build_email1_prompt(lead: Lead, agency_name: str, sender_name: str) -> str:
    days = lead.days_running
    num_ads = lead.num_ads_running
    copy_snippet = lead.ad_copy_snippet or "(no ad copy available)"
    gpt_analysis = lead.gpt_copy_analysis or ""
    first_name = lead.first_name

    return (
        f"Write Email 1 (Day 1 — The Observation) for a cold outreach sequence.\n\n"
        f"Recipient first name: {first_name}\n"
        f"Brand: {lead.brand_name}\n"
        f"Their website: {lead.website_url or '(unknown)'}\n"
        f"Ad copy snippet: \"{copy_snippet}\"\n"
        f"Days running: {days}\n"
        f"Number of active ads: {num_ads}\n"
        f"Ad copy analysis: {gpt_analysis}\n"
        f"Sender: {sender_name} from {agency_name}\n\n"
        f"Angle: 'I noticed something specific about your ads...'\n"
        f"Max 120 words for the body. Subject line should be curious, not salesy.\n\n"
        f"Return JSON: {{\"subject\": \"<subject>\", \"body\": \"<email body>\"}}"
    )


def _build_email2_prompt(
    lead: Lead,
    agency_name: str,
    sender_name: str,
    case_study_brand: str,
    case_study_result: str,
) -> str:
    return (
        f"Write Email 2 (Day 4 — The Proof) for {lead.brand_name}.\n\n"
        f"Recipient first name: {lead.first_name}\n"
        f"Brand: {lead.brand_name}\n"
        f"Sender: {sender_name} from {agency_name}\n"
        f"Case study brand: {case_study_brand}\n"
        f"Case study result: {case_study_result}\n\n"
        f"Angle: Share a relevant result from a similar ecom brand.\n"
        f"Reference the case study naturally — one concrete, specific number.\n"
        f"Max 100 words for the body.\n\n"
        f"Return JSON: {{\"subject\": \"<subject>\", \"body\": \"<email body>\"}}"
    )


def _build_email3_prompt(lead: Lead, agency_name: str, sender_name: str) -> str:
    return (
        f"Write Email 3 (Day 9 — The Soft Close) for {lead.brand_name}.\n\n"
        f"Recipient first name: {lead.first_name}\n"
        f"Brand: {lead.brand_name}\n"
        f"Sender: {sender_name} from {agency_name}\n\n"
        f"Angle: Last touchpoint. Low pressure. One simple ask — a quick call or reply.\n"
        f"Acknowledge you've reached out twice. No guilt-tripping.\n"
        f"Max 80 words for the body.\n\n"
        f"Return JSON: {{\"subject\": \"<subject>\", \"body\": \"<email body>\"}}"
    )


# ── Gemini call ──────────────────────────────────────────────────────────────

@with_retry(max_attempts=3, min_wait=1.0, max_wait=15.0)
def _call_gemini(prompt: str, model: genai.GenerativeModel) -> dict:
    """Call Gemini and parse JSON response."""
    _limiter.acquire_sync()

    try:
        full_prompt = f"{_SYSTEM_INSTRUCTION}\n\n{prompt}"
        resp = model.generate_content(
            full_prompt,
            generation_config=GenerationConfig(
                temperature=0.7,
                max_output_tokens=400,
                response_mime_type="application/json",
            )
        )
        raw = resp.text or "{}"
        return json.loads(raw)
    except Exception as exc:
        # Handle rate limits
        if "429" in str(exc) or "quota" in str(exc).lower():
            logger.warning("Gemini rate limit — backing off 60s")
            time.sleep(60)
            raise
        if isinstance(exc, json.JSONDecodeError):
            logger.warning("Gemini returned invalid JSON: %s", exc)
            raise RuntimeError("Invalid JSON from Gemini") from exc
        logger.error("Gemini API error: %s", exc)
        raise


def _fallback_email(seq_num: int, lead: Lead) -> dict:
    """Return a generic template email if GPT fails."""
    templates = {
        1: {
            "subject": f"Quick question about your {lead.brand_name} ads",
            "body": (
                f"Hi {lead.first_name},\n\n"
                f"I noticed {lead.brand_name} has been running Meta ads for {lead.days_running} days. "
                f"I had a thought about your creative strategy that might be worth sharing.\n\n"
                f"Would you be open to a quick chat?\n\n"
                f"Best,"
            ),
        },
        2: {
            "subject": f"What we did for a similar brand",
            "body": (
                f"Hi {lead.first_name},\n\n"
                f"Wanted to share a quick result — we recently helped a similar ecom brand "
                f"significantly improve their ROAS. Happy to share specifics if useful.\n\n"
                f"Worth a quick call?\n\nBest,"
            ),
        },
        3: {
            "subject": f"Closing the loop — {lead.brand_name}",
            "body": (
                f"Hi {lead.first_name},\n\n"
                f"Last note from me. If the timing isn't right, totally understand.\n\n"
                f"If you ever want to explore improving your Meta ROAS, I'm here.\n\nBest,"
            ),
        },
    }
    return templates[seq_num]


# ── Public API ────────────────────────────────────────────────────────────────

def generate_email(
    lead: Lead,
    model: genai.GenerativeModel,
    agency_name: str,
    sender_name: str,
    case_study_brand: str,
    case_study_result: str,
) -> OutreachSequence:
    """
    Generate a 3-email cold outreach sequence for one lead using Gemini.

    Parameters
    ----------
    lead:               Scored Lead object.
    model:              Gemini GenerativeModel instance.
    agency_name:        Your agency name (used in email sign-off).
    sender_name:        Your name.
    case_study_brand:   Name of a reference client for Email 2.
    case_study_result:  The result achieved, e.g. "620% ROAS in 6 weeks".

    Returns
    -------
    OutreachSequence with three EmailMessage objects.
    """
    sequences = []

    prompts = [
        _build_email1_prompt(lead, agency_name, sender_name),
        _build_email2_prompt(lead, agency_name, sender_name, case_study_brand, case_study_result),
        _build_email3_prompt(lead, agency_name, sender_name),
    ]

    for i, prompt in enumerate(prompts, start=1):
        try:
            data = _call_gemini(prompt, model)
            msg = EmailMessage(
                subject=data.get("subject", f"Follow up #{i}"),
                body=data.get("body", ""),
            )
        except Exception as exc:
            logger.error(
                "Gemini email generation failed for '%s' email %d: %s — using fallback",
                lead.brand_name, i, exc,
            )
            fallback = _fallback_email(i, lead)
            msg = EmailMessage(subject=fallback["subject"], body=fallback["body"])

        sequences.append(msg)

    return OutreachSequence(email_1=sequences[0], email_2=sequences[1], email_3=sequences[2])


def generate_emails_batch(
    leads: List[Lead],
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.0-flash-exp",
) -> List[Lead]:
    """
    Generate email sequences for all leads in the list.

    Parameters
    ----------
    leads:      HOT (and optionally WARM) scored leads.
    api_key:    Gemini API key (falls back to settings if None).
    model_name: Gemini model name.

    Returns
    -------
    Leads with outreach field populated.
    """
    if not api_key:
        from config.settings import get_settings
        cfg = get_settings()
        api_key = cfg.gemini_api_key
        agency_name = cfg.agency_name
        sender_name = cfg.agency_sender_name
        case_study_brand = cfg.agency_case_study_brand
        case_study_result = cfg.agency_case_study_result
    else:
        from config.settings import get_settings
        cfg = get_settings()
        agency_name = cfg.agency_name
        sender_name = cfg.agency_sender_name
        case_study_brand = cfg.agency_case_study_brand
        case_study_result = cfg.agency_case_study_result

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    generated = 0

    for lead in leads:
        try:
            lead.outreach = generate_email(
                lead,
                model,
                agency_name,
                sender_name,
                case_study_brand,
                case_study_result,
            )
            generated += 1
            logger.debug("Generated email sequence for '%s'", lead.brand_name)
        except Exception as exc:
            logger.error("Failed to generate emails for '%s': %s", lead.brand_name, exc)

    logger.info("Email generation complete: %d/%d leads", generated, len(leads))
    return leads
