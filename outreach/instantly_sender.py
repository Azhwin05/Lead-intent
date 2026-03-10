"""
outreach/instantly_sender.py
──────────────────────────────
Sends qualified leads and their 3-email sequences to Instantly.ai
via the v1 REST API.

Only leads with a valid contact_email are sent.
All results are logged to logs/outreach.log.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import requests

from models.lead import Lead, OutreachStatus
from utils.logging_setup import get_logger
from utils.rate_limiter import instantly_limiter
from utils.retry import with_retry

logger = get_logger(__name__)

_INSTANTLY_ADD_LEAD_URL = "https://api.instantly.ai/api/v1/lead/add"
_limiter = instantly_limiter()


# ── API helpers ───────────────────────────────────────────────────────────────

def _build_lead_payload(
    lead: Lead,
    api_key: str,
    campaign_id: str,
) -> dict:
    """Construct the Instantly.ai lead payload from a Lead object."""
    first = lead.first_name
    last = ""
    if lead.contact_name:
        parts = lead.contact_name.split(maxsplit=1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ""

    payload: dict = {
        "api_key": api_key,
        "campaign_id": campaign_id,
        "skip_if_in_workspace": True,
        "leads": [
            {
                "email": lead.contact_email,
                "first_name": first,
                "last_name": last,
                "company_name": lead.brand_name,
                "website": lead.website_url or "",
                "custom_variables": {
                    "roas_score": str(lead.roas_risk_score or 0),
                    "days_running": str(lead.days_running),
                    "lead_tier": lead.lead_tier.value if lead.lead_tier else "UNKNOWN",
                    "num_ads": str(lead.num_ads_running),
                    "copy_analysis": (lead.gpt_copy_analysis or "")[:200],
                },
            }
        ],
    }

    # Optionally attach email sequence as personalization variables
    if lead.outreach:
        payload["leads"][0]["custom_variables"].update(
            {
                "email1_subject": lead.outreach.email_1.subject,
                "email1_body": lead.outreach.email_1.body[:500],
                "email2_subject": lead.outreach.email_2.subject,
                "email3_subject": lead.outreach.email_3.subject,
            }
        )

    return payload


@with_retry(max_attempts=3, min_wait=2.0, max_wait=20.0)
def _post_to_instantly(payload: dict, api_key: str) -> bool:
    """
    POST one lead to Instantly.ai.
    Returns True on success, raises on failure (triggering retry).
    """
    _limiter.acquire_sync()

    try:
        resp = requests.post(
            _INSTANTLY_ADD_LEAD_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        if resp.status_code == 401:
            raise PermissionError("Instantly.ai API key invalid (401). Check INSTANTLY_API_KEY.")
        if resp.status_code == 429:
            logger.warning("Instantly rate limit (429) — backing off")
            raise RuntimeError("429 from Instantly")
        if resp.status_code == 400:
            logger.warning("Instantly 400 Bad Request: %s", resp.text[:200])
            return False  # don't retry 400s — likely bad data
        resp.raise_for_status()

        data = resp.json()
        if data.get("status") == "success" or resp.status_code in (200, 201):
            return True

        logger.warning("Unexpected Instantly response: %s", data)
        return False

    except PermissionError:
        raise  # don't retry auth failures
    except requests.RequestException as exc:
        logger.warning("Instantly request error: %s", exc)
        raise


# ── Public API ────────────────────────────────────────────────────────────────

def add_lead_to_instantly(
    lead: Lead,
    api_key: Optional[str] = None,
    campaign_id: Optional[str] = None,
) -> bool:
    """
    Add a single lead (with email sequence) to an Instantly.ai campaign.

    Parameters
    ----------
    lead:        Scored + email-generated Lead object.
    api_key:     Instantly API key (falls back to settings).
    campaign_id: Instantly campaign ID (falls back to settings).

    Returns
    -------
    True if successfully added, False otherwise.
    """
    if not api_key or not campaign_id:
        from config.settings import get_settings
        cfg = get_settings()
        api_key = api_key or cfg.instantly_api_key
        campaign_id = campaign_id or cfg.instantly_campaign_id

    if not lead.contact_email:
        logger.debug("Skipping '%s' — no contact email", lead.brand_name)
        return False

    payload = _build_lead_payload(lead, api_key, campaign_id)

    try:
        success = _post_to_instantly(payload, api_key)
        if success:
            lead.outreach_status = OutreachStatus.SENT
            logger.info(
                "Sent to Instantly: %s <%s> [score=%d]",
                lead.brand_name,
                lead.contact_email,
                lead.roas_risk_score or 0,
            )
        return success
    except PermissionError as exc:
        logger.error("Auth error — stopping Instantly sends: %s", exc)
        raise
    except Exception as exc:
        logger.error("Failed to add '%s' to Instantly: %s", lead.brand_name, exc)
        return False


def send_batch(
    leads: List[Lead],
    api_key: Optional[str] = None,
    campaign_id: Optional[str] = None,
) -> Dict[str, int]:
    """
    Send all qualifying HOT leads to Instantly.ai.

    Parameters
    ----------
    leads:       List of scored + email-generated leads.
    api_key:     Instantly API key.
    campaign_id: Campaign ID.

    Returns
    -------
    Dict with keys: sent, failed, skipped.
    """
    sent = failed = skipped = 0

    for lead in leads:
        if not lead.contact_email:
            skipped += 1
            continue

        try:
            ok = add_lead_to_instantly(lead, api_key, campaign_id)
            if ok:
                sent += 1
            else:
                failed += 1
        except PermissionError:
            # Auth failure — abort entire batch
            failed += len(leads) - sent - skipped - failed
            break
        except Exception as exc:
            failed += 1
            logger.error("Batch send error for '%s': %s", lead.brand_name, exc)

    logger.info(
        "Instantly batch complete: %d sent | %d failed | %d skipped (no email)",
        sent, failed, skipped,
    )
    return {"sent": sent, "failed": failed, "skipped": skipped}
