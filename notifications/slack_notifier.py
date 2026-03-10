"""
notifications/slack_notifier.py
────────────────────────────────
Slack notification module using Slack Block Kit.

Two notification types:
  1. send_daily_summary()   — posted after each pipeline run
  2. send_hot_lead_alert()  — posted immediately for 9-10 scored leads
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List, Optional

import requests

from models.lead import Lead, PipelineStats
from utils.logging_setup import get_logger
from utils.retry import with_retry

logger = get_logger(__name__)


# ── Low-level webhook sender ──────────────────────────────────────────────────

@with_retry(max_attempts=3, min_wait=2.0, max_wait=15.0)
def _post_to_slack(webhook_url: str, payload: dict) -> bool:
    """POST a Block Kit payload to a Slack Incoming Webhook."""
    try:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        if resp.status_code == 200 and resp.text == "ok":
            return True
        logger.warning("Slack webhook returned %d: %s", resp.status_code, resp.text[:100])
        if resp.status_code == 400:
            # Invalid payload — don't retry
            return False
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Slack webhook request failed: %s", exc)
        raise
    return False


# ── Colour helper ─────────────────────────────────────────────────────────────

def _run_color(hot_leads: int) -> str:
    """Return a hex color for the daily summary attachment side-bar."""
    if hot_leads >= 6:
        return "#2eb67d"   # green
    if hot_leads >= 1:
        return "#ecb22e"   # yellow
    return "#e01e5a"       # red


# ── Block Kit builders ────────────────────────────────────────────────────────

def _build_daily_summary_blocks(stats: PipelineStats) -> dict:
    today = stats.run_date.strftime("%A, %B %d %Y")
    color = _run_color(stats.hot_leads)

    stat_lines = [
        f"Brands scraped:    *{stats.scraped}*",
        f"Contacts enriched: *{stats.enriched}*",
        f"Leads scored:      *{stats.scored}*",
        f"HOT leads (8+):    *{stats.hot_leads}*",
        f"Emails generated:  *{stats.emails_generated}*",
        f"Sent to Instantly: *{stats.outreach_sent}*",
        f"Airtable new:      *{stats.airtable_created}*",
        f"Airtable updated:  *{stats.airtable_updated}*",
    ]

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Daily Lead Gen Report — {today}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(stat_lines),
            },
        },
    ]

    if stats.errors:
        error_text = "\n".join(f"• {e}" for e in stats.errors[:5])
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Pipeline Errors:*\n{error_text}",
                },
            }
        )

    blocks.append({"type": "divider"})

    return {
        "attachments": [
            {
                "color": color,
                "blocks": blocks,
            }
        ]
    }


def _build_hot_lead_blocks(lead: Lead, airtable_base_id: Optional[str] = None) -> dict:
    score = lead.roas_risk_score or 0
    tier = lead.lead_tier.value if lead.lead_tier else "HOT"

    airtable_btn = None
    if lead.airtable_record_id and airtable_base_id:
        airtable_url = (
            f"https://airtable.com/{airtable_base_id}/"
            f"tblXXXXXXXXXXXXXX/{lead.airtable_record_id}"
        )
        airtable_btn = {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View in Airtable"},
                    "url": airtable_url,
                    "action_id": "open_airtable",
                }
            ],
        }

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"HOT LEAD ALERT — Score {score}/10",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Brand:*\n{lead.brand_name}"},
                {"type": "mrkdwn", "text": f"*Website:*\n{lead.website_url or 'N/A'}"},
                {"type": "mrkdwn", "text": f"*Score:*\n{score}/10 ({tier})"},
                {
                    "type": "mrkdwn",
                    "text": f"*Contact:*\n{lead.contact_name or 'Unknown'} — {lead.contact_email or 'No email'}",
                },
            ],
        },
    ]

    if lead.gpt_copy_analysis:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Why they're a hot lead:*\n_{lead.gpt_copy_analysis}_",
                },
            }
        )

    score_breakdown = lead.score_breakdown
    if score_breakdown:
        breakdown_text = (
            f"Creative fatigue: {score_breakdown.creative_fatigue}/2  |  "
            f"Ad volume: {score_breakdown.ad_volume}/2  |  "
            f"Copy quality: {score_breakdown.copy_quality}/2  |  "
            f"Traffic gap: {score_breakdown.traffic_gap}/2  |  "
            f"Biz size: {score_breakdown.business_size}/2"
        )
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": breakdown_text}],
            }
        )

    if airtable_btn:
        blocks.append(airtable_btn)

    return {
        "attachments": [
            {
                "color": "#e01e5a",  # red — urgent
                "blocks": blocks,
            }
        ]
    }


# ── Public API ────────────────────────────────────────────────────────────────

def send_daily_summary(
    stats: PipelineStats,
    webhook_url: Optional[str] = None,
) -> bool:
    """
    Post the daily pipeline run summary to Slack.

    Parameters
    ----------
    stats:       PipelineStats object populated by main.py.
    webhook_url: Slack Incoming Webhook URL (falls back to settings).

    Returns
    -------
    True if message posted successfully, False otherwise.
    """
    if not webhook_url:
        from config.settings import get_settings
        webhook_url = get_settings().slack_webhook_url

    payload = _build_daily_summary_blocks(stats)

    try:
        ok = _post_to_slack(webhook_url, payload)
        if ok:
            logger.info("Daily Slack summary posted successfully.")
        else:
            logger.warning("Daily Slack summary failed to post.")
        return ok
    except Exception as exc:
        logger.error("send_daily_summary error: %s", exc)
        return False


def send_hot_lead_alert(
    lead: Lead,
    webhook_url: Optional[str] = None,
    airtable_base_id: Optional[str] = None,
) -> bool:
    """
    Post an immediate alert for a HOT lead (score 9-10).

    Parameters
    ----------
    lead:             The lead that triggered the alert.
    webhook_url:      Slack Incoming Webhook URL.
    airtable_base_id: Used to build a deep link to the Airtable record.

    Returns
    -------
    True if posted successfully, False otherwise.
    """
    if not webhook_url:
        from config.settings import get_settings
        cfg = get_settings()
        webhook_url = cfg.slack_webhook_url
        airtable_base_id = airtable_base_id or cfg.airtable_base_id

    payload = _build_hot_lead_blocks(lead, airtable_base_id)

    try:
        ok = _post_to_slack(webhook_url, payload)
        if ok:
            logger.info(
                "Hot lead alert sent for '%s' (score %d)",
                lead.brand_name,
                lead.roas_risk_score or 0,
            )
        return ok
    except Exception as exc:
        logger.error("send_hot_lead_alert error for '%s': %s", lead.brand_name, exc)
        return False


def send_error_alert(message: str, webhook_url: Optional[str] = None) -> bool:
    """Send a simple error alert to Slack. Used by the scheduler on crashes."""
    if not webhook_url:
        try:
            from config.settings import get_settings
            webhook_url = get_settings().slack_webhook_url
        except Exception:
            return False

    payload = {
        "attachments": [
            {
                "color": "#e01e5a",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Pipeline Error:*\n{message}",
                        },
                    }
                ],
            }
        ]
    }
    try:
        return _post_to_slack(webhook_url, payload)
    except Exception:
        return False
