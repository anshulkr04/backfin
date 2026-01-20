#!/usr/bin/env python3
"""
Daily Data Collection and Notification Cron Manager

This script manages scheduled tasks for:
1. Daily data collection (Corporate Actions, Deals) at 7:00 PM
2. Hourly insider trading data collection (every hour)
3. Daily watchlist digest emails to users at 12:00 AM (midnight)

The script uses APScheduler to run these tasks reliably with proper error handling,
logging, and retry mechanisms.

Usage:
    # Run the scheduler (keeps running)
    python3 daily_cron_manager.py
    
    # Test individual jobs
    python3 daily_cron_manager.py --test corporate_actions
    python3 daily_cron_manager.py --test deals
    python3 daily_cron_manager.py --test insider_trading
    python3 daily_cron_manager.py --test watchlist_digest

Setup as a system service (recommended):
    1. Copy this script to a permanent location
    2. Create a systemd service (see bottom of file for example)
    3. Enable: sudo systemctl enable backfin-cron.service
    4. Start: sudo systemctl start backfin-cron.service

Or use with nohup:
    nohup python3 daily_cron_manager.py >> /var/log/backfin/cron.log 2>&1 &
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Third-party imports
try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
except ImportError:
    print("❌ APScheduler not installed. Install with: pip install apscheduler")
    sys.exit(1)

from dotenv import load_dotenv

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"
SERVICES_DIR = BASE_DIR / "src" / "services" / "exchange_data"

# Setup logging
LOG_DIR = BASE_DIR / "logs" / "cron"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'cron_manager_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('CronManager')

# Load environment variables
load_dotenv()


# ============================================================================
# JOB DEFINITIONS
# ============================================================================

def run_corporate_actions_collection():
    """Collect daily corporate actions data from NSE and BSE"""
    logger.info("=" * 80)
    logger.info("🏢 CORPORATE ACTIONS DATA COLLECTION STARTED")
    logger.info("=" * 80)
    
    try:
        # Add path for imports
        sys.path.insert(0, str(SERVICES_DIR / "corporate_actions"))
        
        from corporate_actions_collector import CorporateActionsCollector
        
        collector = CorporateActionsCollector()
        # Collect data for next 7 days forward (standard behavior)
        collector.run(days_forward=7)
        
        logger.info("✅ Corporate Actions collection completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Corporate Actions collection failed: {e}", exc_info=True)
        raise


def run_deals_collection():
    """Collect daily bulk and block deals from NSE and BSE"""
    logger.info("=" * 80)
    logger.info("💼 DEALS DATA COLLECTION STARTED")
    logger.info("=" * 80)
    
    try:
        # Add path for imports
        sys.path.insert(0, str(SERVICES_DIR / "deals_management"))
        
        from deals_detector import get_supabase_client, download_all_deals, deduplicate_deals, insert_deals_to_table
        import pandas as pd
        
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Download and normalize (defaults to today)
        nse_bulk, nse_block, bse_bulk, bse_block = download_all_deals()
        
        # Deduplicate
        bulk_final, block_final = deduplicate_deals(nse_bulk, nse_block, bse_bulk, bse_block)
        
        # Combine all final deals
        all_deals = pd.concat([bulk_final, block_final], ignore_index=True)
        
        # Insert directly into deals table
        insert_deals_to_table(all_deals, supabase)
        
        logger.info("✅ Deals collection completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Deals collection failed: {e}", exc_info=True)
        raise


def run_insider_trading_collection():
    """Collect daily insider trading data from NSE and BSE"""
    logger.info("=" * 80)
    logger.info("🔍 INSIDER TRADING DATA COLLECTION STARTED")
    logger.info("=" * 80)
    
    try:
        # Add path for imports
        sys.path.insert(0, str(SERVICES_DIR / "insider_trading"))
        
        from insider_trading_detector import InsiderTradingManager
        
        manager = InsiderTradingManager()
        # Run for today's date (default behavior)
        manager.run()
        
        logger.info("✅ Insider Trading collection completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Insider Trading collection failed: {e}", exc_info=True)
        raise


def run_watchlist_digest():
    """Send daily watchlist digest emails to users"""
    logger.info("=" * 80)
    logger.info("📧 WATCHLIST DIGEST EMAIL STARTED")
    logger.info("=" * 80)
    
    try:
        # Add scripts directory to path
        sys.path.insert(0, str(SCRIPTS_DIR))
        
        # Import and run the digest sender
        import send_daily_digest
        
        # Run the main function from send_daily_digest
        send_daily_digest.main()
        
        logger.info("✅ Watchlist digest emails sent successfully")
        
    except Exception as e:
        logger.error(f"❌ Watchlist digest failed: {e}", exc_info=True)
        raise


def run_daily_data_collections():
    """Run corporate actions and deals collection jobs sequentially at 7:00 PM"""
    logger.info("\n" + "=" * 80)
    logger.info("🚀 STARTING DAILY DATA COLLECTIONS (7:00 PM)")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    # Track success/failure
    results = {
        'corporate_actions': False,
        'deals': False
    }
    
    # Run each collection job (insider trading runs separately every hour)
    jobs = [
        ('corporate_actions', run_corporate_actions_collection),
        ('deals', run_deals_collection)
    ]
    
    for job_name, job_func in jobs:
        try:
            job_func()
            results[job_name] = True
        except Exception as e:
            logger.error(f"❌ {job_name} failed but continuing with other jobs")
            results[job_name] = False
    
    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("\n" + "=" * 80)
    logger.info("📊 DAILY DATA COLLECTION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Start Time:          {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"End Time:            {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Duration:            {duration:.1f} seconds")
    logger.info(f"Corporate Actions:   {'✅ Success' if results['corporate_actions'] else '❌ Failed'}")
    logger.info(f"Deals:               {'✅ Success' if results['deals'] else '❌ Failed'}")
    logger.info("=" * 80)


# ============================================================================
# SCHEDULER EVENT HANDLERS
# ============================================================================

def job_listener(event):
    """Log job execution events"""
    if event.exception:
        logger.error(f"❌ Job {event.job_id} failed with exception: {event.exception}")
    else:
        logger.info(f"✅ Job {event.job_id} completed successfully")


# ============================================================================
# MAIN SCHEDULER SETUP
# ============================================================================

def create_scheduler():
    """Create and configure the APScheduler instance"""
    scheduler = BlockingScheduler()
    
    # Add event listener
    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    
    # ========================================
    # DAILY DATA COLLECTION - 7:00 PM Daily
    # (Corporate Actions and Deals only)
    # ========================================
    scheduler.add_job(
        run_daily_data_collections,
        trigger=CronTrigger(hour=19, minute=0),  # 7:00 PM
        id='daily_data_collection',
        name='Daily Data Collection (Corporate Actions, Deals)',
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600  # Allow 1 hour grace period if missed
    )
    logger.info("✓ Scheduled: Corporate Actions & Deals at 7:00 PM daily")
    
    # ========================================
    # INSIDER TRADING - Every Hour
    # ========================================
    scheduler.add_job(
        run_insider_trading_collection,
        trigger=CronTrigger(minute=0),  # Every hour at :00
        id='hourly_insider_trading',
        name='Hourly Insider Trading Collection',
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300  # Allow 5 minute grace period if missed
    )
    logger.info("✓ Scheduled: Insider Trading every hour at :00")
    
    # ========================================
    # WATCHLIST DIGEST - 12:00 AM Daily
    # ========================================
    scheduler.add_job(
        run_watchlist_digest,
        trigger=CronTrigger(hour=0, minute=0),  # 12:00 AM (midnight)
        id='watchlist_digest',
        name='Daily Watchlist Digest Emails',
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600  # Allow 1 hour grace period if missed
    )
    logger.info("✓ Scheduled: Watchlist Digest at 12:00 AM daily")
    
    return scheduler


# ============================================================================
# TEST MODE
# ============================================================================

def test_job(job_name: str):
    """Test a specific job by running it immediately"""
    logger.info(f"\n🧪 TEST MODE: Running {job_name}")
    
    jobs = {
        'corporate_actions': run_corporate_actions_collection,
        'deals': run_deals_collection,
        'insider_trading': run_insider_trading_collection,
        'watchlist_digest': run_watchlist_digest,
        'daily_data': run_daily_data_collections
    }
    
    if job_name not in jobs:
        logger.error(f"❌ Unknown job: {job_name}")
        logger.info(f"Available jobs: {', '.join(jobs.keys())}")
        sys.exit(1)
    
    try:
        jobs[job_name]()
        logger.info(f"✅ Test completed successfully for {job_name}")
    except Exception as e:
        logger.error(f"❌ Test failed for {job_name}: {e}", exc_info=True)
        sys.exit(1)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Daily Data Collection and Notification Cron Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run scheduler (keeps running)
  python3 daily_cron_manager.py
  
  # Test individual jobs
  python3 daily_cron_manager.py --test corporate_actions
  python3 daily_cron_manager.py --test deals
  python3 daily_cron_manager.py --test insider_trading
  python3 daily_cron_manager.py --test watchlist_digest
  python3 daily_cron_manager.py --test daily_data

Schedule:
  - Corporate Actions & Deals: 7:00 PM daily
  - Insider Trading: Every hour (on the hour)
  - Watchlist Digest: 12:00 AM daily (Midnight)
        """
    )
    
    parser.add_argument(
        '--test',
        type=str,
        choices=['corporate_actions', 'deals', 'insider_trading', 'watchlist_digest', 'daily_data'],
        help='Test a specific job by running it immediately'
    )
    
    args = parser.parse_args()
    
    # Test mode
    if args.test:
        test_job(args.test)
        return
    
    # Normal scheduler mode
    logger.info("=" * 80)
    logger.info("🚀 BACKFIN DAILY CRON MANAGER")
    logger.info("=" * 80)
    logger.info("Starting scheduled jobs...")
    logger.info("")
    logger.info("Schedule:")
    logger.info("  📊 Corporate Actions & Deals: 7:00 PM daily")
    logger.info("")
    logger.info("  🔍 Insider Trading:           Every hour at :00")
    logger.info("")
    logger.info("  📧 Watchlist Digest:          12:00 AM daily")
    logger.info("")
    logger.info("=" * 80)
    logger.info("")
    
    # Create and start scheduler
    scheduler = create_scheduler()
    
    try:
        logger.info("✅ Scheduler started successfully")
        logger.info("Press Ctrl+C to stop\n")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("\n⏹️  Scheduler stopped by user")
        scheduler.shutdown()
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Scheduler crashed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()


# ============================================================================
# SYSTEMD SERVICE EXAMPLE (save as /etc/systemd/system/backfin-cron.service)
# ============================================================================
"""
[Unit]
Description=Backfin Daily Data Collection and Notification Service
After=network.target

[Service]
Type=simple
User=anshulkumar
WorkingDirectory=/Users/anshulkumar/backfin
Environment="PATH=/Users/anshulkumar/backfin/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/Users/anshulkumar/backfin/.venv/bin/python3 /Users/anshulkumar/backfin/daily_cron_manager.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/backfin/cron.log
StandardError=append:/var/log/backfin/cron_error.log

[Install]
WantedBy=multi-user.target
"""

# ============================================================================
# ALTERNATIVE: RUN WITH NOHUP
# ============================================================================
"""
# Create log directory
mkdir -p /var/log/backfin

# Start in background
nohup python3 /Users/anshulkumar/backfin/daily_cron_manager.py >> /var/log/backfin/cron.log 2>&1 &

# Save PID
echo $! > /var/log/backfin/cron.pid

# Check if running
ps -p $(cat /var/log/backfin/cron.pid)

# Stop
kill $(cat /var/log/backfin/cron.pid)
"""
