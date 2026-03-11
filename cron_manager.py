#!/usr/bin/env python3
"""
Backfin Cron Manager — APScheduler-based

Schedule:
    - Company change detection + auto-apply:  6:00 AM daily
    - Corporate Actions & Deals collection:   7:00 PM daily
    - Insider Trading collection:             Every hour at :00
    - Watchlist Digest emails:                12:00 AM daily (midnight)

Usage:
    python3 cron_manager.py                       # Run scheduler
    python3 cron_manager.py --test <job>           # Test a specific job
    python3 cron_manager.py --run-now              # Run all jobs once, then exit

Run in background on VM:
    nohup python3 cron_manager.py >> logs/cron/cron.log 2>&1 &
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from dotenv import load_dotenv

# ============================================================================
# Setup
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"
SERVICES_DIR = BASE_DIR / "src" / "services" / "exchange_data"

LOG_DIR = BASE_DIR / "logs" / "cron"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'cron_{datetime.now():%Y%m%d}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger('cron')

load_dotenv()

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# ============================================================================
# Job Functions
# ============================================================================

def job_corporate_actions():
    """Collect corporate actions data (NSE + BSE)"""
    logger.info("--- Corporate Actions collection ---")
    sys.path.insert(0, str(SERVICES_DIR / "corporate_actions"))
    from corporate_actions_collector import CorporateActionsCollector
    collector = CorporateActionsCollector()
    collector.run(days_forward=7)
    logger.info("Corporate Actions done")


def job_deals():
    """Collect bulk and block deals (NSE + BSE)"""
    logger.info("--- Deals collection ---")
    sys.path.insert(0, str(SERVICES_DIR / "deals_management"))
    from deals_detector import get_supabase_client, download_all_deals, deduplicate_deals, insert_deals_to_table
    import pandas as pd

    supabase = get_supabase_client()
    nse_bulk, nse_block, bse_bulk, bse_block = download_all_deals()
    bulk_final, block_final = deduplicate_deals(nse_bulk, nse_block, bse_bulk, bse_block)
    all_deals = pd.concat([bulk_final, block_final], ignore_index=True)
    insert_deals_to_table(all_deals, supabase)
    logger.info("Deals done")


def job_insider_trading():
    """Collect insider trading data (NSE + BSE)"""
    logger.info("--- Insider Trading collection ---")
    sys.path.insert(0, str(SERVICES_DIR / "insider_trading"))
    from insider_trading_detector import InsiderTradingManager
    manager = InsiderTradingManager()
    manager.run()
    logger.info("Insider Trading done")


def job_watchlist_digest():
    """Send daily watchlist digest emails"""
    logger.info("--- Watchlist Digest ---")
    sys.path.insert(0, str(SCRIPTS_DIR))
    import send_daily_digest
    send_daily_digest.main()
    logger.info("Watchlist Digest done")


def job_company_changes():
    """Detect and auto-apply company changes from exchange data"""
    logger.info("--- Company Change Detection & Auto-Apply ---")
    sys.path.insert(0, str(SERVICES_DIR / "company_management"))
    from auto_apply_changes import detect_and_apply_changes
    detect_and_apply_changes(keep_files=False, dry_run=False)
    logger.info("Company Changes done")


def job_daily_7pm():
    """Combined 7 PM job: corporate actions + deals"""
    logger.info("=== Daily 7 PM collections ===")
    start = datetime.now()

    for name, fn in [("corporate_actions", job_corporate_actions), ("deals", job_deals)]:
        try:
            fn()
        except Exception as e:
            logger.error(f"{name} failed: {e}", exc_info=True)

    duration = (datetime.now() - start).total_seconds()
    logger.info(f"=== 7 PM collections finished in {duration:.0f}s ===")


# Map for --test flag
JOB_MAP = {
    "corporate_actions": job_corporate_actions,
    "deals":             job_deals,
    "insider_trading":   job_insider_trading,
    "watchlist_digest":  job_watchlist_digest,
    "company_changes":   job_company_changes,
    "daily_7pm":         job_daily_7pm,
}


# ============================================================================
# Scheduler
# ============================================================================

def _job_listener(event):
    """Log job execution results"""
    if event.exception:
        logger.error(f"Job {event.job_id} failed: {event.exception}")
    else:
        logger.info(f"Job {event.job_id} completed successfully")


def create_scheduler() -> BlockingScheduler:
    """Create APScheduler with all cron jobs registered."""
    scheduler = BlockingScheduler()
    scheduler.add_listener(_job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    # Company changes — 6:00 AM daily
    scheduler.add_job(
        job_company_changes,
        trigger=CronTrigger(hour=6, minute=0),
        id='company_changes',
        name='Company Change Detection & Auto-Apply',
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # Corporate actions + deals — 7:00 PM daily
    scheduler.add_job(
        job_daily_7pm,
        trigger=CronTrigger(hour=19, minute=0),
        id='daily_7pm',
        name='Daily Data Collection (Corporate Actions + Deals)',
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # Insider trading — every hour at :00
    scheduler.add_job(
        job_insider_trading,
        trigger=CronTrigger(minute=0),
        id='insider_trading',
        name='Hourly Insider Trading Collection',
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )

    # Watchlist digest — midnight
    scheduler.add_job(
        job_watchlist_digest,
        trigger=CronTrigger(hour=0, minute=0),
        id='watchlist_digest',
        name='Daily Watchlist Digest Emails',
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    return scheduler


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Backfin Cron Manager")
    parser.add_argument(
        "--test",
        choices=list(JOB_MAP.keys()),
        help="Run a single job immediately for testing",
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run all jobs once immediately, then exit",
    )
    args = parser.parse_args()

    if args.test:
        logger.info(f"Test run: {args.test}")
        try:
            JOB_MAP[args.test]()
            logger.info("Test completed successfully")
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            sys.exit(1)
        return

    if args.run_now:
        logger.info("Running all jobs once...")
        for name, fn in JOB_MAP.items():
            if name == "daily_7pm":
                continue  # skip combined — individual ones already run
            logger.info(f"Running: {name}")
            try:
                fn()
            except Exception as e:
                logger.error(f"{name} failed: {e}", exc_info=True)
        logger.info("All jobs finished")
        return

    # Normal scheduler mode
    logger.info("=" * 60)
    logger.info("Backfin Cron Manager")
    logger.info("=" * 60)
    logger.info("Schedule:")
    logger.info("  company_changes        6:00 AM daily")
    logger.info("  daily_7pm              7:00 PM daily  (corp actions + deals)")
    logger.info("  insider_trading        every hour at :00")
    logger.info("  watchlist_digest       12:00 AM daily")
    logger.info("=" * 60)

    scheduler = create_scheduler()
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
