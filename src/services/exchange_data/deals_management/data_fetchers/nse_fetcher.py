#!/usr/bin/env python3
"""
NSE Data Fetcher - Downloads bulk and block deals from NSE.
"""

import json
import time
import random
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class NSEDataFetcher:
    """Fetcher for NSE bulk and block deals data."""
    
    BASE_URL = "https://www.nseindia.com"
    
    def __init__(self):
        """Initialize NSE session with proper headers."""
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
    
    def establish_session(self) -> bool:
        """
        Visit NSE pages to get cookies (mandatory before API call).
        
        Returns:
            True if session established successfully, False otherwise
        """
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
            logger.info("NSE session established successfully.")
            return True
        except Exception as e:
            logger.error(f"NSE session establishment failed: {e}")
            return False
    
    def parse_response(self, response) -> dict:
        """
        Handle compressed or normal JSON responses.
        
        Args:
            response: requests Response object
            
        Returns:
            Parsed JSON data
        """
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
    
    def fetch_deals(self, deal_type: str, date_str: Optional[str] = None) -> Optional[List[Dict]]:
        """
        Fetch bulk or block deals from NSE.
        
        Args:
            deal_type: 'bulk_deals' or 'block_deals'
            date_str: Date string in DD-MM-YYYY format (defaults to today)
            
        Returns:
            List of deal records or None if fetch failed
        """
        if not self.establish_session():
            return None
        
        # Default to today in India timezone
        if not date_str:
            today = datetime.utcnow() + timedelta(hours=5, minutes=30)
            date_str = today.strftime("%d-%m-%Y")
        
        logger.info(f"Fetching NSE {deal_type} for {date_str}")
        
        api_url = f"{self.BASE_URL}/api/historicalOR/bulk-block-short-deals"
        params = {
            'optionType': deal_type,
            'from': date_str,
            'to': date_str
        }
        headers = {
            'referer': f"{self.BASE_URL}/companies-listing/corporate-filings-insider-trading"
        }
        
        try:
            resp = self.session.get(api_url, params=params, headers=headers, timeout=30)
            logger.info(f"NSE API Response: {resp.status_code}")
            
            if resp.status_code == 200:
                data = self.parse_response(resp)
                records = data.get("data", []) if isinstance(data, dict) else []
                logger.info(f"Retrieved {len(records)} NSE {deal_type} records.")
                return records
            else:
                logger.error(f"Failed to fetch NSE data: {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching NSE {deal_type}: {e}")
            return None
    
    def fetch_bulk_deals(self, date_str: Optional[str] = None) -> Optional[List[Dict]]:
        """
        Fetch bulk deals.
        
        Args:
            date_str: Date string in DD-MM-YYYY format
            
        Returns:
            List of bulk deal records
        """
        return self.fetch_deals('bulk_deals', date_str)
    
    def fetch_block_deals(self, date_str: Optional[str] = None) -> Optional[List[Dict]]:
        """
        Fetch block deals.
        
        Args:
            date_str: Date string in DD-MM-YYYY format
            
        Returns:
            List of block deal records
        """
        return self.fetch_deals('block_deals', date_str)
    
    def close(self):
        """Close the session."""
        self.session.close()
