"""
scrapers/meta_ad_library.py
────────────────────────────
Async Playwright scraper for Meta's Ad Library.

Searches by keyword, extracts active eCommerce brand advertisers,
and returns a list of Lead objects filtered to brands with
days_running >= MIN_DAYS_RUNNING.

Anti-detection measures:
  • Realistic viewport & user-agent
  • Random delays between actions (jitter)
  • Headless chromium with stealth args
  • Per-keyword retry on timeout
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from models.lead import AdCreativeType, Lead
from utils.logging_setup import get_logger
from utils.retry import with_async_retry

logger = get_logger(__name__)

_DATA_DIR = Path("data")
_DATA_DIR.mkdir(exist_ok=True)

_AD_LIBRARY_URL = "https://www.facebook.com/ads/library/"

# CSS selectors — Meta changes these occasionally; list multiple fallbacks
_AD_CARD_SELECTORS = [
    "[data-testid='ad-archive-renderer']",
    "._7jyr",
    "._9vow",
    ".x1dr75xp",  # 2024 class
]
_PAGE_NAME_SELECTORS = ["._8jtf", "._7jys a", "strong", "h2"]
_AD_BODY_SELECTORS = ["._7jyt", "._4-u2", "[data-testid='ad-creative-body']"]
_AD_DATE_SELECTORS = ["._7jyq", "._8mce", "[data-testid='ad-start-date']"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _random_delay(min_s: float = 1.5, max_s: float = 4.0) -> float:
    return random.uniform(min_s, max_s)


def _parse_days_running(date_str: str) -> int:
    """Convert 'Started running on Month D, YYYY' → days since start."""
    try:
        # Try common Meta date formats
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
            try:
                start = datetime.strptime(date_str.strip(), fmt).date()
                return (date.today() - start).days
            except ValueError:
                continue
    except Exception:
        pass
    return 0


def _extract_domain(url: str) -> Optional[str]:
    """Extract clean domain from a URL string."""
    if not url:
        return None
    url = re.sub(r"^https?://(www\.)?", "", url)
    return url.split("/")[0].lower() or None


# ── Browser bootstrap ─────────────────────────────────────────────────────────

async def _create_context(playwright: Playwright, headless: bool = True) -> BrowserContext:
    """Launch Chromium with stealth settings."""
    browser: Browser = await playwright.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--disable-extensions",
        ],
    )
    context = await browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        timezone_id="America/New_York",
        java_script_enabled=True,
        accept_downloads=False,
    )
    # Remove webdriver flag
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return context


# ── Per-card data extraction ──────────────────────────────────────────────────

async def _extract_ad_data(card, keyword: str) -> Optional[Dict]:
    """
    Extract structured data from a single ad card element.
    Returns None if required fields cannot be found.
    """
    try:
        # Brand / page name
        brand_name = None
        for sel in _PAGE_NAME_SELECTORS:
            try:
                el = await card.query_selector(sel)
                if el:
                    brand_name = (await el.inner_text()).strip()
                    if brand_name:
                        break
            except Exception:
                continue

        if not brand_name:
            return None

        # Page URL
        page_url: Optional[str] = None
        try:
            link = await card.query_selector("a[href*='facebook.com']")
            if link:
                page_url = await link.get_attribute("href")
        except Exception:
            pass

        # Website URL (often in CTA button)
        website_url: Optional[str] = None
        try:
            cta = await card.query_selector("a[href*='l.facebook.com']")
            if not cta:
                cta = await card.query_selector("a[data-testid='ad-cta-link']")
            if cta:
                raw = await cta.get_attribute("href") or ""
                # Decode l.facebook.com redirect
                m = re.search(r"u=([^&]+)", raw)
                if m:
                    from urllib.parse import unquote
                    website_url = unquote(m.group(1))
                else:
                    website_url = raw if raw.startswith("http") else None
        except Exception:
            pass

        # Ad ID
        ad_id: Optional[str] = None
        try:
            ad_id_el = await card.query_selector("[data-ad-id]")
            if ad_id_el:
                ad_id = await ad_id_el.get_attribute("data-ad-id")
        except Exception:
            pass

        # Start date + days running
        ad_start_date = ""
        days_running = 0
        try:
            for sel in _AD_DATE_SELECTORS:
                el = await card.query_selector(sel)
                if el:
                    text = await el.inner_text()
                    if text:
                        ad_start_date = text.strip()
                        days_running = _parse_days_running(ad_start_date)
                        break
        except Exception:
            pass

        # Ad creative type
        creative_type = AdCreativeType.UNKNOWN
        try:
            if await card.query_selector("video"):
                creative_type = AdCreativeType.VIDEO
            elif await card.query_selector("[data-testid='ad-carousel']"):
                creative_type = AdCreativeType.CAROUSEL
            elif await card.query_selector("img"):
                creative_type = AdCreativeType.IMAGE
        except Exception:
            pass

        # Ad copy snippet
        ad_copy = ""
        try:
            for sel in _AD_BODY_SELECTORS:
                el = await card.query_selector(sel)
                if el:
                    ad_copy = (await el.inner_text()).strip()[:200]
                    if ad_copy:
                        break
        except Exception:
            pass

        # Num ads running (shown in page header area)
        num_ads = 1  # default to 1 (this ad is running)

        return {
            "brand_name": brand_name,
            "page_url": page_url,
            "website_url": website_url,
            "ad_id": ad_id or f"ad_{keyword}_{brand_name[:10].replace(' ', '_')}",
            "ad_start_date": ad_start_date,
            "days_running": days_running,
            "ad_creative_type": creative_type.value,
            "ad_copy_snippet": ad_copy,
            "num_ads_running": num_ads,
        }
    except Exception as exc:
        logger.debug("Failed to extract ad card data: %s", exc)
        return None


# ── Per-keyword scrape ────────────────────────────────────────────────────────

@with_async_retry(max_attempts=3, min_wait=5.0, max_wait=30.0)
async def _scrape_keyword(
    page: Page,
    keyword: str,
    max_results: int,
    min_days_running: int,
    timeout_ms: int,
) -> List[Dict]:
    """Navigate to Meta Ad Library, search for keyword, extract ads."""
    logger.info("Scraping keyword: '%s'", keyword)
    results: List[Dict] = []

    url = (
        f"{_AD_LIBRARY_URL}"
        f"?active_status=active&ad_type=all&country=US"
        f"&q={keyword.replace(' ', '+')}&search_type=keyword_unordered"
    )

    try:
        await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        await asyncio.sleep(_random_delay(2.0, 5.0))

        # Handle cookie/consent dialogs
        for dismiss_sel in [
            "[data-testid='cookie-policy-manage-dialog-accept-button']",
            "button[title='Allow all cookies']",
            "button[data-cookiebanner='accept_button']",
        ]:
            try:
                btn = await page.query_selector(dismiss_sel)
                if btn:
                    await btn.click()
                    await asyncio.sleep(1.0)
                    break
            except Exception:
                pass

        # Scroll to load more cards
        scroll_rounds = min(max_results // 10, 8)
        for _ in range(scroll_rounds):
            await page.keyboard.press("End")
            await asyncio.sleep(_random_delay(1.5, 3.0))

        # Try each selector for ad cards
        cards = []
        for sel in _AD_CARD_SELECTORS:
            try:
                cards = await page.query_selector_all(sel)
                if cards:
                    break
            except Exception:
                continue

        if not cards:
            logger.warning("No ad cards found for keyword '%s' — page may have changed", keyword)
            return []

        logger.info("Found %d ad cards for '%s'", len(cards), keyword)

        for card in cards[:max_results]:
            data = await _extract_ad_data(card, keyword)
            if data and data["days_running"] >= min_days_running:
                results.append(data)
            await asyncio.sleep(_random_delay(0.1, 0.3))

    except PlaywrightTimeoutError:
        logger.error("Timeout scraping keyword '%s'", keyword)
        raise
    except Exception as exc:
        logger.error("Error scraping keyword '%s': %s", keyword, exc)
        raise

    return results


# ── Public API ────────────────────────────────────────────────────────────────

async def scrape_meta_ads(
    keyword_list: List[str],
    max_results: int = 100,
    min_days_running: int = 30,
    headless: bool = True,
    timeout_ms: int = 30_000,
) -> List[Lead]:
    """
    Scrape Meta Ad Library for active eCommerce advertisers.

    Parameters
    ----------
    keyword_list:     List of ecom-related search terms.
    max_results:      Max ads to collect per keyword.
    min_days_running: Only include ads running at least this many days.
    headless:         Run browser headlessly.
    timeout_ms:       Playwright page-level timeout.

    Returns
    -------
    Deduplicated list of Lead objects (deduped on page_url).
    """
    all_raw: List[Dict] = []
    seen_urls: set = set()

    async with async_playwright() as playwright:
        context = await _create_context(playwright, headless=headless)
        page = await context.new_page()
        page.set_default_timeout(timeout_ms)

        try:
            for keyword in keyword_list:
                try:
                    kw_results = await _scrape_keyword(
                        page, keyword, max_results, min_days_running, timeout_ms
                    )
                    for r in kw_results:
                        key = r.get("page_url") or r["brand_name"]
                        if key not in seen_urls:
                            seen_urls.add(key)
                            all_raw.append(r)
                except Exception as exc:
                    logger.error("Skipping keyword '%s' after retries: %s", keyword, exc)
                finally:
                    await asyncio.sleep(_random_delay(3.0, 7.0))  # cooldown between keywords
        finally:
            await context.close()

    # ── Save raw output ───────────────────────────────────────
    today = date.today().isoformat()
    raw_path = _DATA_DIR / f"raw_ads_{today}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_raw, f, indent=2, default=str)
    logger.info("Saved %d raw ads to %s", len(all_raw), raw_path)

    # ── Convert to Lead models ────────────────────────────────
    leads: List[Lead] = []
    for raw in all_raw:
        try:
            lead = Lead(
                brand_name=raw["brand_name"],
                page_url=raw.get("page_url"),
                website_url=raw.get("website_url"),
                ad_id=raw.get("ad_id"),
                ad_start_date=raw.get("ad_start_date"),
                days_running=raw.get("days_running", 0),
                ad_creative_type=AdCreativeType(raw.get("ad_creative_type", "unknown")),
                ad_copy_snippet=raw.get("ad_copy_snippet"),
                num_ads_running=raw.get("num_ads_running", 1),
            )
            leads.append(lead)
        except Exception as exc:
            logger.warning("Could not build Lead from raw ad data: %s | %s", exc, raw)

    logger.info(
        "Scrape complete: %d unique leads (days_running >= %d)",
        len(leads),
        min_days_running,
    )
    return leads


# ── CLI entry-point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from utils.logging_setup import configure_logging

    configure_logging(logging.DEBUG)

    test_keywords = ["skincare", "supplements", "fitness"]
    logger.info("Running quick test with keywords: %s", test_keywords)

    leads = asyncio.run(
        scrape_meta_ads(test_keywords, max_results=20, min_days_running=30)
    )

    print(f"\n{'='*60}")
    print(f"Total leads found: {len(leads)}")
    for lead in leads[:2]:
        print(f"\n  Brand:        {lead.brand_name}")
        print(f"  Website:      {lead.website_url}")
        print(f"  Days Running: {lead.days_running}")
        print(f"  Num Ads:      {lead.num_ads_running}")
        print(f"  Copy Snippet: {lead.ad_copy_snippet[:80] if lead.ad_copy_snippet else 'N/A'}...")
