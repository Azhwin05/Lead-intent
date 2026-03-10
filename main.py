"""
main.py
────────
Master pipeline orchestrator for the eCommerce Lead Gen System.

Runs the complete pipeline end-to-end:
  1. Scrape  — Meta Ad Library
  2. Enrich  — Apollo.io + Similarweb
  3. Score   — ROAS risk scoring (GPT-4o)
  4. Emails  — Generate personalised sequences (GPT-4o)
  5. Save    — Airtable upsert
  6. Send    — Instantly.ai outreach
  7. Notify  — Slack summary + hot lead alerts

Usage:
  python main.py                         # Full live run
  python main.py --dry-run               # No emails, no Airtable writes
  python main.py --dry-run --limit 5     # Test with 5 leads only
  python main.py --min-score 8           # Override score threshold
  python main.py --keywords "skincare,supplements"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

# ── Configure logging before any other imports ────────────────────────────────
from utils.logging_setup import configure_logging, get_logger

_today = date.today().isoformat()
configure_logging(
    level=logging.INFO,
    log_file=f"pipeline_{_today}.log",
)
logger = get_logger(__name__)

# ── Now import pipeline modules ───────────────────────────────────────────────
from config.settings import get_settings
from models.lead import Lead, PipelineStats
from scrapers.meta_ad_library import scrape_meta_ads
from enrichment.apollo_enricher import enrich_with_apollo
from enrichment.similarweb_enricher import enrich_with_traffic
from scoring.roas_scorer import score_leads, filter_hot_leads
from outreach.email_writer import generate_emails_batch
from outreach.instantly_sender import send_batch
from storage.airtable_client import get_airtable_client
from notifications.slack_notifier import (
    send_daily_summary,
    send_hot_lead_alert,
    send_error_alert,
)


# ── Pipeline steps ────────────────────────────────────────────────────────────

def step_scrape(
    keywords: List[str],
    max_results: int,
    min_days_running: int,
) -> List[Lead]:
    logger.info("STEP 1 — Scraping Meta Ad Library for %d keywords...", len(keywords))
    leads = asyncio.run(
        scrape_meta_ads(
            keyword_list=keywords,
            max_results=max_results,
            min_days_running=min_days_running,
        )
    )
    logger.info("STEP 1 DONE — Scraped %d unique brands.", len(leads))
    return leads


def step_enrich(leads: List[Lead]) -> List[Lead]:
    logger.info("STEP 2 — Enriching %d brands with Apollo + Similarweb...", len(leads))
    leads = enrich_with_apollo(leads)
    leads = enrich_with_traffic(leads)
    enriched_count = sum(1 for l in leads if l.contact_email)
    logger.info("STEP 2 DONE — %d brands have contact emails.", enriched_count)
    return leads


def step_score(leads: List[Lead], min_score: int) -> tuple[List[Lead], List[Lead]]:
    logger.info("STEP 3 — Scoring %d brands for ROAS risk...", len(leads))
    scored = score_leads(leads)
    hot = filter_hot_leads(scored, min_score=min_score)
    logger.info(
        "STEP 3 DONE — Scored %d brands | %d qualify (score >= %d).",
        len(scored),
        len(hot),
        min_score,
    )
    return scored, hot


def step_generate_emails(hot_leads: List[Lead]) -> List[Lead]:
    logger.info("STEP 4 — Generating email sequences for %d HOT leads...", len(hot_leads))
    hot_leads = generate_emails_batch(hot_leads)
    with_emails = sum(1 for l in hot_leads if l.outreach)
    logger.info("STEP 4 DONE — Generated emails for %d leads.", with_emails)
    return hot_leads


def step_save_to_airtable(leads: List[Lead]) -> dict:
    logger.info("STEP 5 — Saving %d leads to Airtable...", len(leads))
    client = get_airtable_client()
    stats = client.save_leads_batch(leads)
    logger.info(
        "STEP 5 DONE — Airtable: %d created | %d updated | %d failed.",
        stats["created"], stats["updated"], stats["failed"],
    )
    return stats


def step_send_outreach(leads: List[Lead]) -> dict:
    logger.info("STEP 6 — Sending %d leads to Instantly.ai...", len(leads))
    stats = send_batch(leads)
    logger.info(
        "STEP 6 DONE — Instantly: %d sent | %d failed | %d skipped.",
        stats["sent"], stats["failed"], stats["skipped"],
    )
    return stats


def step_notify(
    pipeline_stats: PipelineStats,
    hot_leads: List[Lead],
    alert_threshold: int,
) -> None:
    logger.info("STEP 7 — Posting Slack notifications...")
    send_daily_summary(pipeline_stats)

    alerts_sent = 0
    for lead in hot_leads:
        if (lead.roas_risk_score or 0) >= alert_threshold:
            send_hot_lead_alert(lead)
            alerts_sent += 1

    logger.info("STEP 7 DONE — Slack summary sent | %d hot lead alerts.", alerts_sent)


# ── CLI argument parser ───────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="eCommerce Lead Gen Pipeline — finds low-ROAS Meta advertisers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run pipeline without writing to Airtable or sending emails.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Only process first N brands per keyword (useful for testing).",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=None,
        metavar="SCORE",
        help="Override minimum ROAS risk score threshold (0-10).",
    )
    parser.add_argument(
        "--keywords",
        type=str,
        default=None,
        metavar="K1,K2,...",
        help="Comma-separated keyword overrides (bypasses settings.py list).",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Console log verbosity (default: INFO).",
    )
    return parser


# ── Main entry point ──────────────────────────────────────────────────────────

def run_pipeline(
    dry_run: bool = False,
    limit: Optional[int] = None,
    min_score: Optional[int] = None,
    keywords: Optional[List[str]] = None,
) -> PipelineStats:
    """
    Execute the full lead generation pipeline.

    Parameters
    ----------
    dry_run:   If True, skips Airtable writes and Instantly sends.
    limit:     Cap on max_results per keyword (for testing).
    min_score: Override minimum score threshold.
    keywords:  Keyword override list.

    Returns
    -------
    PipelineStats object summarising the run.
    """
    cfg = get_settings()
    stats = PipelineStats()

    _kw = keywords or cfg.scrape_keywords
    _max = limit or cfg.max_leads_per_run
    _min_days = cfg.min_days_running
    _threshold = min_score if min_score is not None else cfg.min_score_threshold
    _alert_threshold = cfg.hot_lead_alert_threshold

    if dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN MODE — no emails will be sent, no data saved")
        logger.info("=" * 60)

    # ── Step 1: Scrape ────────────────────────────────────────
    raw_leads: List[Lead] = []
    try:
        raw_leads = step_scrape(_kw, _max, _min_days)
        stats.scraped = len(raw_leads)
    except Exception as exc:
        logger.error("STEP 1 FAILED: %s", exc, exc_info=True)
        stats.record_error("scrape", str(exc))

    if not raw_leads:
        logger.warning("No leads scraped — check scraper logs. Aborting pipeline.")
        _post_summary_and_return(stats, dry_run)
        return stats

    # ── Step 2: Enrich ────────────────────────────────────────
    enriched: List[Lead] = raw_leads
    try:
        enriched = step_enrich(raw_leads)
        stats.enriched = sum(1 for l in enriched if l.contact_email)
    except Exception as exc:
        logger.error("STEP 2 FAILED: %s", exc, exc_info=True)
        stats.record_error("enrich", str(exc))

    # ── Step 3: Score ─────────────────────────────────────────
    scored: List[Lead] = []
    hot_leads: List[Lead] = []
    try:
        scored, hot_leads = step_score(enriched, _threshold)
        stats.scored = len(scored)
        stats.hot_leads = len(hot_leads)
    except Exception as exc:
        logger.error("STEP 3 FAILED: %s", exc, exc_info=True)
        stats.record_error("score", str(exc))

    if not hot_leads:
        logger.info("No qualifying leads this run (min_score=%d).", _threshold)
        _post_summary_and_return(stats, dry_run)
        return stats

    # ── Step 4: Generate emails ───────────────────────────────
    try:
        hot_leads = step_generate_emails(hot_leads)
        stats.emails_generated = sum(1 for l in hot_leads if l.outreach)
    except Exception as exc:
        logger.error("STEP 4 FAILED: %s", exc, exc_info=True)
        stats.record_error("email_gen", str(exc))

    # ── Step 5: Save to Airtable ──────────────────────────────
    if not dry_run:
        try:
            airtable_result = step_save_to_airtable(hot_leads)
            stats.airtable_created = airtable_result["created"]
            stats.airtable_updated = airtable_result["updated"]
            stats.airtable_failed = airtable_result["failed"]
        except Exception as exc:
            logger.error("STEP 5 FAILED: %s", exc, exc_info=True)
            stats.record_error("airtable", str(exc))
    else:
        logger.info("STEP 5 SKIPPED (dry-run) — would save %d leads to Airtable.", len(hot_leads))

    # ── Step 6: Send outreach ─────────────────────────────────
    if not dry_run:
        try:
            outreach_result = step_send_outreach(hot_leads)
            stats.outreach_sent = outreach_result["sent"]
            stats.outreach_failed = outreach_result["failed"]
            stats.outreach_skipped = outreach_result["skipped"]
        except Exception as exc:
            logger.error("STEP 6 FAILED: %s", exc, exc_info=True)
            stats.record_error("outreach", str(exc))
    else:
        logger.info(
            "STEP 6 SKIPPED (dry-run) — would send %d leads to Instantly.", len(hot_leads)
        )

    # ── Step 7: Notify ────────────────────────────────────────
    _post_summary_and_return(stats, dry_run, hot_leads=hot_leads, alert_threshold=_alert_threshold)

    # ── Final summary log ─────────────────────────────────────
    logger.info(
        "Pipeline complete: %d scraped | %d enriched | %d scored | "
        "%d HOT | %d emails | %d saved | %d sent",
        stats.scraped,
        stats.enriched,
        stats.scored,
        stats.hot_leads,
        stats.emails_generated,
        stats.airtable_created + stats.airtable_updated,
        stats.outreach_sent,
    )
    return stats


def _post_summary_and_return(
    stats: PipelineStats,
    dry_run: bool,
    hot_leads: Optional[List[Lead]] = None,
    alert_threshold: int = 9,
) -> None:
    """Always send Slack summary, even in dry-run or partial failure."""
    if dry_run:
        logger.info("STEP 7 SKIPPED (dry-run) — Slack notifications suppressed.")
        return
    try:
        step_notify(stats, hot_leads or [], alert_threshold)
    except Exception as exc:
        logger.error("STEP 7 FAILED: %s", exc, exc_info=True)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = build_arg_parser()
    args = parser.parse_args()

    # Adjust log level if requested
    if args.log_level != "INFO":
        logging.getLogger().setLevel(getattr(logging, args.log_level))

    kw_override = None
    if args.keywords:
        kw_override = [k.strip() for k in args.keywords.split(",") if k.strip()]

    try:
        final_stats = run_pipeline(
            dry_run=args.dry_run,
            limit=args.limit,
            min_score=args.min_score,
            keywords=kw_override,
        )
        sys.exit(0 if not final_stats.errors else 1)
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        logger.critical("Unhandled pipeline error: %s", exc, exc_info=True)
        try:
            send_error_alert(f"Pipeline crashed: {exc}")
        except Exception:
            pass
        sys.exit(1)
