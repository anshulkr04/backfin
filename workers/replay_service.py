#!/usr/bin/env python3
"""
replay_service.py

A dedicated service script for continuous replay of unprocessed announcements.
This script runs continuously and checks for unprocessed data every minute.

Usage:
    python replay_service.py [options]

This is a wrapper around replay.py that's designed to run as a service.
"""

import sys
import signal
import logging
from replay import run_continuous_replay, genai_client

# Configure logging for service
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("replay_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("replay_service")

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

def main():
    """Main service entry point"""
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting Backfin Replay Service...")
    logger.info("This service will continuously check for unprocessed announcements")
    
    # Check if AI processing is available
    enable_ai = genai_client is not None
    if not enable_ai:
        logger.warning("AI processing unavailable - will only handle Supabase uploads")
    
    try:
        # Run continuous replay with default settings optimized for service
        run_continuous_replay(
            batch=200,              # Process up to 200 rows per cycle
            retries=3,              # Retry failed uploads 3 times
            enable_ai=enable_ai,    # Enable AI if available
            check_interval=60       # Check every minute
        )
    except Exception as e:
        logger.error(f"Service failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()