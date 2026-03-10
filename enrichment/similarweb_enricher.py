"""
enrichment/similarweb_enricher.py
──────────────────────────────────
Enriches leads with traffic data (monthly visits, paid traffic %, bounce rate)
via the Similarweb API.

Fallback: if SIMILARWEB_API_KEY is not configured, or the domain is not found,
a simple heuristic estimate is used based on the number of active ads and
employee count — so the pipeline never stalls.
"""

from __future__ import annotations

import logging
import random
from typing import List, Optional

import requests

from models.lead import Lead
from utils.logging_setup import get_logger
from utils.rate_limiter import similarweb_limiter
from utils.retry import with_retry

logger = get_logger(__name__)

_SIMILARWEB_BASE = "https://api.similarweb.com/v1/website/{domain}/traffic-and-engagement/visits"
_OVERVIEW_BASE   = "https://api.similarweb.com/v1/website/{domain}/traffic-sources/overview"

_limiter = similarweb_limiter()


# ── Heuristic fallback ────────────────────────────────────────────────────────

def _heuristic_traffic(lead: Lead) -> dict:
    """
    Estimate traffic signals when Similarweb API is unavailable.

    Logic:
      • employee count >50 → large brand  (200K–2M visits)
      • employee count 11-50 → medium     (50K–200K visits)
      • else (tiny / unknown)             (5K–50K visits)
    • paid_traffic_percentage is biased upward for brands with many ads
    """
    emp = lead.company_employee_count or 0

    if emp > 50:
        monthly_visits = random.randint(200_000, 2_000_000)
    elif emp > 10:
        monthly_visits = random.randint(50_000, 200_000)
    else:
        monthly_visits = random.randint(5_000, 50_000)

    # More ads running → more paid traffic reliance (heuristic)
    base_paid = 30.0
    ad_factor = min(lead.num_ads_running * 3.0, 40.0)
    paid_pct = min(base_paid + ad_factor + random.uniform(-5, 5), 95.0)

    bounce = random.uniform(40.0, 70.0)

    logger.debug(
        "Using heuristic traffic for '%s': ~%d visits, %.1f%% paid",
        lead.brand_name,
        monthly_visits,
        paid_pct,
    )
    return {
        "monthly_visits": monthly_visits,
        "paid_traffic_percentage": round(paid_pct, 1),
        "bounce_rate": round(bounce, 1),
    }


# ── API call ──────────────────────────────────────────────────────────────────

@with_retry(max_attempts=2, min_wait=2.0, max_wait=10.0)
def _fetch_similarweb(domain: str, api_key: str) -> Optional[dict]:
    """
    Fetch traffic overview from Similarweb for one domain.
    Returns parsed traffic dict or None on failure.
    """
    _limiter.acquire_sync()

    url = _OVERVIEW_BASE.format(domain=domain)
    params = {
        "api_key": api_key,
        "main_domain_only": "true",
        "granularity": "monthly",
        "start_date": "2024-01",
        "end_date": "2024-12",
        "country": "us",
    }

    try:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code == 401:
            raise PermissionError("Similarweb API key invalid (401)")
        if resp.status_code == 404:
            logger.debug("Similarweb: domain '%s' not found", domain)
            return None
        if resp.status_code == 429:
            logger.warning("Similarweb rate limit hit — backing off")
            raise RuntimeError("429 — retrying")
        resp.raise_for_status()
        return resp.json()
    except PermissionError:
        raise
    except requests.RequestException as exc:
        logger.warning("Similarweb request failed for '%s': %s", domain, exc)
        raise


def _parse_similarweb_response(data: dict) -> dict:
    """Extract relevant metrics from Similarweb API response."""
    visits = data.get("total_visits") or 0
    sources = data.get("traffic_sources") or {}
    paid_pct = (sources.get("paid_search", 0) + sources.get("display_ads", 0)) * 100
    bounce = data.get("bounce_rate", 0) * 100 if data.get("bounce_rate", 0) <= 1 else data.get("bounce_rate", 0)
    return {
        "monthly_visits": int(visits),
        "paid_traffic_percentage": round(min(paid_pct, 100.0), 1),
        "bounce_rate": round(bounce, 1),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def enrich_with_traffic(
    brand_list: List[Lead],
    api_key: Optional[str] = None,
) -> List[Lead]:
    """
    Enrich each Lead with monthly traffic, paid traffic %, and bounce rate.

    Falls back to heuristic estimates if:
      • SIMILARWEB_API_KEY is not set
      • Domain not found in Similarweb database
      • API call fails after retries

    Parameters
    ----------
    brand_list: Leads from Apollo enrichment stage.
    api_key:    Similarweb API key (falls back to settings if None).

    Returns
    -------
    Leads with traffic fields populated.
    """
    if not api_key:
        from config.settings import get_settings
        api_key = get_settings().similarweb_api_key  # may be None

    api_enriched = 0
    heuristic_used = 0

    for lead in brand_list:
        traffic: Optional[dict] = None

        if api_key and lead.domain:
            try:
                raw = _fetch_similarweb(lead.domain, api_key)
                if raw:
                    traffic = _parse_similarweb_response(raw)
                    api_enriched += 1
            except PermissionError:
                logger.error("Similarweb auth failed — switching to heuristics for all remaining.")
                api_key = None  # stop trying
            except Exception as exc:
                logger.warning("Similarweb failed for '%s': %s", lead.brand_name, exc)

        if not traffic:
            traffic = _heuristic_traffic(lead)
            heuristic_used += 1

        lead.monthly_visits = traffic["monthly_visits"]
        lead.paid_traffic_percentage = traffic["paid_traffic_percentage"]
        lead.bounce_rate = traffic["bounce_rate"]

    logger.info(
        "Traffic enrichment complete: %d via Similarweb API, %d via heuristics",
        api_enriched,
        heuristic_used,
    )
    return brand_list
