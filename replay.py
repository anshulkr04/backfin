#!/usr/bin/env python3
"""
replay_unsent_to_supabase.py

Replay unsent local `corporatefilings` rows to Supabase for a given date.

Usage:
    python replay_unsent_to_supabase.py --date 2025-09-26

This script expects the local SQLite DB at ./data/bse_raw.db (relative to this file).
It reads environment variables SUPABASE_URL2 and SUPABASE_KEY2 (or SUPABASE_SERVICE_ROLE_KEY).
"""

import os
import argparse
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

# Optional import - if you don't have supabase python client, the script will exit early.
try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("replay_unsent")

# Local DB path (same layout as your scraper)
LOCAL_DB_PATH = Path(__file__).parent / "data" / "bse_raw.db"

# Supabase env vars (match names used in your main script)
SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_KEY2")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def get_supabase_client():
    """Return a supabase client if env vars present, else None."""
    if create_client is None:
        logger.error("supabase package not available. Please `pip install supabase` to enable Supabase uploads.")
        return None

    if not SUPABASE_URL or not (SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY):
        logger.error("Supabase credentials not found in environment (SUPABASE_URL2 / SUPABASE_KEY2).")
        return None

    key = SUPABASE_SERVICE_ROLE_KEY if SUPABASE_SERVICE_ROLE_KEY else SUPABASE_KEY
    try:
        client = create_client(SUPABASE_URL, key)
        logger.info("Supabase client initialized")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None

def mark_local_sent_to_supabase(conn, corp_id, db_path=None):
    """Mark local corporatefilings row as sent_to_supabase = 1 and set timestamp."""
    try:
        now_ts = datetime.now(timezone.utc).isoformat()
        cur = conn.cursor()
        cur.execute(
            "UPDATE corporatefilings SET sent_to_supabase = 1, sent_to_supabase_at = ? WHERE corp_id = ?",
            (now_ts, corp_id)
        )
        conn.commit()
        logger.debug(f"Marked local corp_id {corp_id} as sent")
        return True
    except Exception as e:
        logger.error(f"Failed to mark local corp_id {corp_id} as sent: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False

def fetch_unsent_rows(conn, date_str, batch=500):
    """
    Fetch rows for the provided date where sent_to_supabase is NULL or 0.
    Date matching is permissive: it checks equality and also prefixes (handles iso and compact formats).
    """
    cur = conn.cursor()
    # Prepare possible date patterns:
    # Accept date like 2025-09-26 or 20250926
    compact = date_str.replace("-", "")
    like_iso = f"{date_str}%"
    like_compact = f"{compact}%"

    query = """
        SELECT * FROM corporatefilings
        WHERE (sent_to_supabase IS NULL OR sent_to_supabase = 0)
        AND (
            date = ?
            OR date LIKE ?
            OR date LIKE ?
        )
        LIMIT ?
    """
    cur.execute(query, (date_str, like_iso, like_compact, batch))
    rows = cur.fetchall()
    return rows

def row_to_payload(row):
    """Convert sqlite row tuple / dict to dict payload for Supabase insert."""
    # row could be a tuple; best to access by index mapping - use column names if available
    # We'll try to detect if row is sqlite3.Row (mapping)
    if isinstance(row, sqlite3.Row):
        get = lambda k: row[k]
    else:
        # Fallback: try index-based mapping (use schema order)
        # Schema order used in earlier script:
        # corp_id, securityid, summary, fileurl, date, ai_summary, category, isin,
        # companyname, symbol, headline, sentiment, company_id, downloaded_pdf_file,
        # pdf_pages, pdf_downloaded_at, ai_processed, ai_processed_at, ai_error,
        # sent_to_supabase, sent_to_supabase_at
        def get(k):
            mapping = {
                "corp_id": 0, "securityid": 1, "summary": 2, "fileurl": 3, "date": 4,
                "ai_summary": 5, "category": 6, "isin": 7, "companyname": 8, "symbol": 9,
                "headline": 10, "sentiment": 11, "company_id": 12
            }
            idx = mapping.get(k)
            return row[idx] if idx is not None and idx < len(row) else None

    payload = {
        "corp_id": get("corp_id"),
        "securityid": get("securityid"),
        "summary": get("summary"),
        "fileurl": get("fileurl"),
        "date": get("date"),
        "ai_summary": get("ai_summary"),
        "category": get("category"),
        "isin": get("isin"),
        "companyname": get("companyname"),
        "symbol": get("symbol"),
        "headline": get("headline"),
        "sentiment": get("sentiment"),
        "company_id": get("company_id"),
    }
    return payload

def replay_unsent_to_supabase(date_str, batch=100, retry_per_row=3, wait_between_retries=2):
    """Main replay function. Returns (attempted, succeeded)."""
    supabase_client = get_supabase_client()
    if not supabase_client:
        logger.error("Supabase client not available. Aborting replay.")
        return 0, 0

    if not LOCAL_DB_PATH.exists():
        logger.error(f"Local DB not found at {LOCAL_DB_PATH}")
        return 0, 0

    conn = sqlite3.connect(str(LOCAL_DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    attempted = 0
    succeeded = 0

    try:
        rows = fetch_unsent_rows(conn, date_str, batch=batch)
        if not rows:
            logger.info("No unsent rows found for date %s", date_str)
            return 0, 0

        logger.info("Found %d unsent rows for date %s (batch=%d)", len(rows), date_str, batch)

        for r in rows:
            attempted += 1
            corp_id = r["corp_id"]
            payload = row_to_payload(r)
            success = False
            last_err = None

            for attempt in range(1, retry_per_row + 1):
                try:
                    # Insert into Supabase
                    supabase_client.table("corporatefilings").insert(payload).execute()
                    # Mark local as sent
                    mark_local_sent_to_supabase(conn, corp_id)
                    succeeded += 1
                    success = True
                    logger.info("Successfully replayed corp_id=%s", corp_id)
                    break
                except Exception as e:
                    last_err = e
                    logger.warning("Attempt %d/%d failed for corp_id %s: %s", attempt, retry_per_row, corp_id, e)
                    time.sleep(wait_between_retries * attempt)

            if not success:
                logger.error("Failed to replay corp_id=%s after %d attempts. Last error: %s", corp_id, retry_per_row, last_err)

        return attempted, succeeded

    finally:
        try:
            conn.close()
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description="Replay unsent local corporatefilings rows to Supabase for a specific date")
    parser.add_argument("--date", required=True, help="Date to replay for (example: 2025-09-26)")
    parser.add_argument("--batch", type=int, default=200, help="Number of rows to fetch in one run (default 200)")
    parser.add_argument("--retries", type=int, default=3, help="Number of retries per row when inserting to Supabase")
    args = parser.parse_args()

    date_str = args.date.strip()
    logger.info("Starting replay for date: %s", date_str)
    attempted, succeeded = replay_unsent_to_supabase(date_str, batch=args.batch, retry_per_row=args.retries)
    logger.info("Replay complete. Attempted: %d, Succeeded: %d", attempted, succeeded)

if __name__ == "__main__":
    main()
