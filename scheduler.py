"""
scheduler.py
─────────────
APScheduler-based daily pipeline runner.

Runs main.py's pipeline every day at the configured hour (default 6 AM local).

Usage:
  python scheduler.py              # Start the scheduler (blocking)
  python scheduler.py --run-now   # Trigger one immediate run then keep scheduling
  python scheduler.py --dry-run   # Pass dry-run to each scheduled run
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from utils.logging_setup import configure_logging, get_logger

configure_logging(log_file="scheduler.log")
logger = get_logger(__name__)


# ── Job function ──────────────────────────────────────────────────────────────

def _run_pipeline_job(dry_run: bool = False) -> None:
    """
    APScheduler job — calls run_pipeline() in-process.

    Isolated in a try/except so a single failed run never kills the scheduler.
    """
    from main import run_pipeline

    logger.info("=" * 60)
    logger.info("Scheduled pipeline starting at %s", datetime.now().isoformat())
    logger.info("=" * 60)

    try:
        stats = run_pipeline(dry_run=dry_run)
        logger.info(
            "Scheduled run finished: %d HOT leads | %d sent | %d errors",
            stats.hot_leads,
            stats.outreach_sent,
            len(stats.errors),
        )
    except Exception as exc:
        logger.error("Scheduled pipeline run failed: %s", exc, exc_info=True)
        try:
            from notifications.slack_notifier import send_error_alert
            send_error_alert(f"Scheduled pipeline crashed: {exc}")
        except Exception:
            pass


# ── Scheduler setup ───────────────────────────────────────────────────────────

def build_scheduler(hour: int, minute: int, dry_run: bool) -> BlockingScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = BlockingScheduler(timezone="local")

    trigger = CronTrigger(hour=hour, minute=minute)
    scheduler.add_job(
        _run_pipeline_job,
        trigger=trigger,
        kwargs={"dry_run": dry_run},
        id="daily_pipeline",
        name="eComm Lead Gen Pipeline",
        max_instances=1,           # Never run two instances simultaneously
        coalesce=True,             # Merge missed runs into one
        misfire_grace_time=3600,   # Allow up to 1h late start
    )

    return scheduler


# ── Signal handlers ───────────────────────────────────────────────────────────

def _handle_shutdown(signum: int, frame: object) -> None:
    """Graceful shutdown on SIGINT / SIGTERM."""
    logger.info("Shutdown signal received — stopping scheduler gracefully...")
    sys.exit(0)


signal.signal(signal.SIGINT, _handle_shutdown)
signal.signal(signal.SIGTERM, _handle_shutdown)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Daily scheduler for the eCommerce Lead Gen Pipeline."
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Execute one pipeline run immediately before starting the schedule.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pass --dry-run to every scheduled pipeline execution.",
    )
    args = parser.parse_args()

    from config.settings import get_settings
    cfg = get_settings()

    hour = cfg.schedule_hour
    minute = cfg.schedule_minute

    scheduler = build_scheduler(hour, minute, dry_run=args.dry_run)

    # Print next run time
    job = scheduler.get_job("daily_pipeline")
    if job and job.next_run_time:
        logger.info(
            "Scheduler started. Next run: %s (daily at %02d:%02d local)",
            job.next_run_time.strftime("%Y-%m-%d %H:%M %Z"),
            hour,
            minute,
        )
    else:
        logger.info("Scheduler started. Daily run at %02d:%02d local.", hour, minute)

    if args.run_now:
        logger.info("--run-now flag set — executing pipeline immediately.")
        _run_pipeline_job(dry_run=args.dry_run)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
