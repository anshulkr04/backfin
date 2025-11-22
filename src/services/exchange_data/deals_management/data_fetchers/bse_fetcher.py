#!/usr/bin/env python3
"""
BSE Data Fetcher - Downloads bulk and block deals from BSE.
"""

import logging
from typing import Optional, List, Dict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


class BSEDataFetcher:
    """Fetcher for BSE bulk and block deals data."""
    
    BULK_URL = "https://www.bseindia.com/markets/equity/EQReports/bulk_deals.aspx"
    BLOCK_URL = "https://www.bseindia.com/markets/equity/EQReports/block_deals.aspx"
    
    def __init__(self, headless: bool = True):
        """
        Initialize BSE fetcher with Selenium.
        
        Args:
            headless: Whether to run browser in headless mode
        """
        self.headless = headless
        self.driver = None
    
    def setup_driver(self):
        """Setup Chrome driver with appropriate options."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        self.driver = webdriver.Chrome(options=chrome_options)
    
    def convert_to_json(self, data: List[List[str]]) -> List[Dict]:
        """
        Convert scraped table data to JSON format.
        
        Args:
            data: List of rows where first row is headers
            
        Returns:
            List of dictionaries with header-value pairs
        """
        if not data or len(data) < 2:
            return []
        
        headers = data[0]
        rows = data[1:]
        return [dict(zip(headers, row)) for row in rows]
    
    def fetch_bulk_deals(self) -> Optional[List[Dict]]:
        """
        Fetch bulk deals from BSE.
        
        Returns:
            List of bulk deal records or None if fetch failed
        """
        if not self.driver:
            self.setup_driver()
        
        try:
            logger.info("Fetching BSE bulk deals...")
            self.driver.get(self.BULK_URL)
            
            # Wait for table to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_gvbulk_deals"))
            )
            
            table = self.driver.find_element(By.ID, "ContentPlaceHolder1_gvbulk_deals")
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            # Extract text from all cells
            data = []
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "th") + row.find_elements(By.TAG_NAME, "td")
                data.append([cell.text.strip() for cell in cells])
            
            records = self.convert_to_json(data)
            logger.info(f"Retrieved {len(records)} BSE bulk deal records.")
            return records
            
        except Exception as e:
            logger.error(f"Error fetching BSE bulk deals: {e}")
            return None
    
    def fetch_block_deals(self) -> Optional[List[Dict]]:
        """
        Fetch block deals from BSE.
        
        Returns:
            List of block deal records or None if fetch failed
        """
        if not self.driver:
            self.setup_driver()
        
        try:
            logger.info("Fetching BSE block deals...")
            self.driver.get(self.BLOCK_URL)
            
            # Wait for table to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_gvblock_deals"))
            )
            
            table = self.driver.find_element(By.ID, "ContentPlaceHolder1_gvblock_deals")
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            # Extract text from all cells
            data = []
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "th") + row.find_elements(By.TAG_NAME, "td")
                data.append([cell.text.strip() for cell in cells])
            
            records = self.convert_to_json(data)
            logger.info(f"Retrieved {len(records)} BSE block deal records.")
            return records
            
        except Exception as e:
            logger.error(f"Error fetching BSE block deals: {e}")
            return None
    
    def close(self):
        """Close the browser driver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
