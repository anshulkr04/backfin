#!/usr/bin/env python3
"""
NSE Bulk/Block/Short-Sell Scraper for Today's Data — Direct Supabase Upload

Usage:
    python nse_today_uploader.py [bulk_deals|block_deals|short_selling]

Examples:
    python nse_today_uploader.py bulk_deals
    python nse_today_uploader.py block_deals
"""

import os
import json
import time
import random
import logging
import requests
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from supabase import create_client
from dotenv import load_dotenv

# ------------------------------------------------------------
# Setup
# ------------------------------------------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("NSEUploader")

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def parse_date_to_iso(date_str):
    """Convert '30-SEP-2025' or '30-09-2025' to '2025-09-30'."""
    fmts = ("%d-%b-%Y", "%d-%m-%Y")
    for fmt in fmts:
        try:
            return datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            continue
    return None

def parse_price_to_4dp(value):
    if value is None or value == "":
        return None
    try:
        d = Decimal(str(value))
        d = d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return str(d)
    except Exception:
        return None

def get_supabase_client():
    SUPABASE_URL = os.environ.get("SUPABASE_URL2") or os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY2")
        or os.environ.get("SUPABASE_ANON_KEY")
    )
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing Supabase credentials")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ------------------------------------------------------------
# NSE Scraper Class
# ------------------------------------------------------------
class NSEBulkDealsScraper:
    BASE_URL = "https://www.nseindia.com"

    def __init__(self):
        self.session = requests.Session()
        self.setup_session()

    def setup_session(self):
        """Set headers similar to real browser requests."""
        self.session.headers.update({
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US,en;q=0.9,hi;q=0.8',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'cors',
        })

    def establish_session(self):
        """Visit NSE pages to get cookies (mandatory before API call)."""
        try:
            logger.info("Establishing NSE session...")
            pages = [
                f"{self.BASE_URL}/",
                f"{self.BASE_URL}/market-data",
                f"{self.BASE_URL}/companies-listing",
                f"{self.BASE_URL}/companies-listing/corporate-filings-insider-trading"
            ]
            for page in pages:
                self.session.get(page, timeout=10)
                time.sleep(random.uniform(1, 3))
            logger.info("Session established successfully.")
            return True
        except Exception as e:
            logger.error(f"Session establishment failed: {e}")
            return False

    def parse_response(self, response):
        """Handle compressed or normal JSON responses."""
        try:
            return response.json()
        except json.JSONDecodeError:
            raw = response.content
            try:
                import brotli
                data = brotli.decompress(raw).decode("utf-8")
                return json.loads(data)
            except Exception:
                import gzip
                data = gzip.decompress(raw).decode("utf-8")
                return json.loads(data)

    def scrape_today(self, option_type="bulk_deals"):
        """Scrape today's data."""
        if not self.establish_session():
            return None

        # India time → date string
        today = datetime.utcnow() + timedelta(hours=5, minutes=30)
        # date_str = today.strftime("%d-%m-%Y")
        date_str = "23-10-2025"

        logger.info(f"Scraping NSE {option_type} for {date_str}")

        api_url = f"{self.BASE_URL}/api/historicalOR/bulk-block-short-deals"
        params = {'optionType': option_type, 'from': date_str, 'to': date_str}

        headers = {'referer': f"{self.BASE_URL}/companies-listing/corporate-filings-insider-trading"}

        resp = self.session.get(api_url, params=params, headers=headers, timeout=30)
        logger.info(f"API Response: {resp.status_code}")

        if resp.status_code == 200:
            data = self.parse_response(resp)
            count = len(data.get("data", [])) if isinstance(data, dict) else 0
            logger.info(f"Retrieved {count} records.")
            return data
        else:
            logger.error(f"Failed to fetch data: {resp.status_code}")
            return None

    def close(self):
        self.session.close()

# ------------------------------------------------------------
# Supabase Upload
# ------------------------------------------------------------
def upload_to_supabase(data_obj, option_type):
    mapping = {
        "bulk_deals": "BULK",
        "block_deals": "BLOCK",
        "short_selling": "SHORT-SELL"
    }
    deal_constant = mapping.get(option_type)

    rows = data_obj.get("data") if isinstance(data_obj, dict) else []
    if not rows:
        logger.warning("No rows found to upload.")
        return

    records = []
    for row in rows:
        date_iso = parse_date_to_iso(row.get("BD_DT_DATE", ""))
        rec = {
            "symbol": row.get("BD_SYMBOL"),
            "securityid": None,
            "date": date_iso,
            "client_name": row.get("BD_CLIENT_NAME"),
            "deal_type": row.get("BD_BUY_SELL"),
            "quantity": row.get("BD_QTY_TRD"),
            "price": parse_price_to_4dp(row.get("BD_TP_WATP")),
            "exchange": "NSE",
            "deal": deal_constant,
        }
        if rec["symbol"] and rec["price"]:
            records.append(rec)

    logger.info(f"Prepared {len(records)} records for insert to Supabase")

    if not records:
        logger.info("No valid records to upload.")
        return

    supabase = get_supabase_client()
    try:
        resp = supabase.table("deals").insert(records).execute()
        inserted = len(resp.data) if getattr(resp, "data", None) else "unknown"
        logger.info(f"Insert successful: {inserted} rows")
    except Exception as e:
        logger.error(f"Supabase insert failed: {e}")

# ------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------
if __name__ == "__main__":
    scraper = NSEBulkDealsScraper()
    try:
        for option_type in ["bulk_deals", "block_deals"]:
            logger.info(f"Starting scrape for {option_type.upper()}...")
            data = scraper.scrape_today(option_type)
            if data:
                upload_to_supabase(data, option_type)
            else:
                logger.warning(f"No data retrieved for {option_type}.")
            time.sleep(3)  # small polite delay between calls
    finally:
        scraper.close()
        logger.info("All NSE uploads completed.")
