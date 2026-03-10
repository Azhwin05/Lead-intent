"""
enrichment/apollo_enricher.py
──────────────────────────────
Enriches scraped brands with decision-maker contact information
via the Apollo.io People Search API.

Rate limiting: 1 request/second (Apollo free tier = 50 req/month).
Usage tracking: persisted to data/apollo_usage.json so we never
silently blow through the monthly quota.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from models.lead import Lead
from utils.logging_setup import get_logger
from utils.rate_limiter import apollo_limiter
from utils.retry import with_retry

logger = get_logger(__name__)

_DATA_DIR = Path("data")
_DATA_DIR.mkdir(exist_ok=True)
_USAGE_FILE = _DATA_DIR / "apollo_usage.json"

_APOLLO_PEOPLE_URL = "https://api.apollo.io/v1/mixed_people/search"
_FREE_TIER_MONTHLY_LIMIT = 50
_TARGET_TITLES = [
    "Founder",
    "Co-Founder",
    "CEO",
    "Chief Executive Officer",
    "CMO",
    "Chief Marketing Officer",
    "Head of Marketing",
    "VP of Marketing",
    "Director of Marketing",
    "Growth Lead",
]

_limiter = apollo_limiter()


# ── Usage tracking ────────────────────────────────────────────────────────────

def _load_usage() -> Dict[str, int]:
    if _USAGE_FILE.exists():
        try:
            return json.loads(_USAGE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _save_usage(usage: Dict[str, int]) -> None:
    _USAGE_FILE.write_text(json.dumps(usage, indent=2), encoding="utf-8")


def _get_monthly_count() -> int:
    usage = _load_usage()
    month_key = date.today().strftime("%Y-%m")
    return usage.get(month_key, 0)


def _increment_usage() -> None:
    usage = _load_usage()
    month_key = date.today().strftime("%Y-%m")
    usage[month_key] = usage.get(month_key, 0) + 1
    _save_usage(usage)


def _check_quota() -> bool:
    """Return False (and log a warning) if monthly quota is reached."""
    count = _get_monthly_count()
    if count >= _FREE_TIER_MONTHLY_LIMIT:
        logger.warning(
            "Apollo monthly limit reached (%d/%d). Skipping enrichment.",
            count,
            _FREE_TIER_MONTHLY_LIMIT,
        )
        return False
    remaining = _FREE_TIER_MONTHLY_LIMIT - count
    if remaining <= 5:
        logger.warning("Apollo quota almost exhausted: %d requests remaining.", remaining)
    return True


# ── API call ──────────────────────────────────────────────────────────────────

@with_retry(max_attempts=3, min_wait=2.0, max_wait=15.0)
def _search_apollo(domain: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Call Apollo People Search for the given domain.
    Returns the first matching person dict, or None.
    """
    _limiter.acquire_sync()

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key,
    }
    payload = {
        "api_key": api_key,
        "q_organization_domains": domain,
        "person_titles": _TARGET_TITLES,
        "per_page": 1,
        "page": 1,
    }

    try:
        resp = requests.post(
            _APOLLO_PEOPLE_URL,
            headers=headers,
            json=payload,
            timeout=20,
        )
        if resp.status_code == 429:
            logger.warning("Apollo rate limit hit (429). Backing off...")
            time.sleep(60)
            raise RuntimeError("Apollo 429 — retrying")
        if resp.status_code == 401:
            raise PermissionError("Apollo API key is invalid (401). Check APOLLO_API_KEY.")
        resp.raise_for_status()
        data = resp.json()
        people = data.get("people", [])
        return people[0] if people else None
    except PermissionError:
        raise
    except requests.RequestException as exc:
        logger.warning("Apollo API request failed: %s", exc)
        raise


# ── Enrichment logic ──────────────────────────────────────────────────────────

def _apply_apollo_data(lead: Lead, person: Optional[Dict[str, Any]]) -> Lead:
    """Mutate lead in-place with Apollo person data."""
    if not person:
        return lead

    # Name
    first = person.get("first_name", "") or ""
    last = person.get("last_name", "") or ""
    lead.contact_name = f"{first} {last}".strip() or None

    lead.contact_title = person.get("title")

    # Email (Apollo may or may not reveal it on free tier)
    email = person.get("email") or ""
    lead.contact_email = email if "@" in email else None

    lead.contact_linkedin = person.get("linkedin_url")

    org = person.get("organization") or {}
    lead.company_employee_count = org.get("estimated_num_employees")
    lead.company_industry = org.get("industry")

    return lead


def enrich_with_apollo(
    brand_list: List[Lead],
    api_key: Optional[str] = None,
) -> List[Lead]:
    """
    Enrich each Lead with decision-maker contact info from Apollo.io.

    Parameters
    ----------
    brand_list: Leads from meta_ad_library scraper.
    api_key:    Apollo API key (falls back to settings if None).

    Returns
    -------
    Leads with contact fields populated where available.
    """
    if not api_key:
        from config.settings import get_settings
        api_key = get_settings().apollo_api_key

    enriched = 0
    skipped_quota = 0
    failed = 0

    for lead in brand_list:
        if not lead.domain:
            logger.debug("Skipping '%s' — no domain found", lead.brand_name)
            continue

        if not _check_quota():
            skipped_quota += 1
            continue

        try:
            person = _search_apollo(lead.domain, api_key)
            _increment_usage()
            _apply_apollo_data(lead, person)
            if lead.contact_email:
                enriched += 1
                logger.debug(
                    "Apollo enriched '%s' → %s (%s)",
                    lead.brand_name,
                    lead.contact_name,
                    lead.contact_email,
                )
            else:
                logger.debug("Apollo returned no contact email for '%s'", lead.brand_name)
        except PermissionError:
            logger.error("Apollo auth failed — stopping enrichment.")
            break
        except Exception as exc:
            failed += 1
            logger.error("Apollo enrichment failed for '%s': %s", lead.brand_name, exc)

    logger.info(
        "Apollo enrichment complete: %d with email, %d skipped (quota), %d failed",
        enriched,
        skipped_quota,
        failed,
    )
    return brand_list
