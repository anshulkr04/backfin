import requests
import json
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import logging
import time
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_bse_company_data(url):
    with requests.Session() as session:
        # Get cookies by visiting the homepage first
        homepage_url = "https://www.bseindia.com"
        session.get(homepage_url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        })

        # Set headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.bseindia.com/",
            "Origin": "https://www.bseindia.com",
            "Connection": "keep-alive",
        }

        try:
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None
        except json.JSONDecodeError:
            print("Error decoding JSON response")
            return None
        
def get_nse_company_data(url):
    """
    Fetch NSE company data from the given API URL.
    
    Args:
        url (str): The NSE API URL to fetch data from
        
    Returns:
        dict: JSON response data if successful, None if failed
    """
    with requests.Session() as session:
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1"
        }
        session.headers.update(headers)

        logger.info("Initializing session...")
        
        try:
            # Step 1: Visit NSE homepage to establish session and get cookies
            logger.info("Visiting NSE homepage...")
            resp = session.get("https://www.nseindia.com/", timeout=30)
            resp.raise_for_status()
            logger.info(f"Homepage status: {resp.status_code}")
            logger.info(f"Cookies received: {len(session.cookies)} cookies")
            
            # Add a small delay to mimic human behavior
            time.sleep(random.uniform(1, 3))
            
            # Step 2: Visit market data page to ensure proper session
            logger.info("Visiting market data page...")
            session.headers.update({
                "Referer": "https://www.nseindia.com/"
            })
            
            market_resp = session.get("https://www.nseindia.com/market-data/live-equity-market", timeout=30)
            market_resp.raise_for_status()
            logger.info(f"Market data page status: {market_resp.status_code}")
            
            # Add another delay
            time.sleep(random.uniform(1, 2))
            
            # Step 3: Visit the specific quote page for the symbol
            symbol = url.split('symbol=')[1].split('&')[0] if 'symbol=' in url else 'RELIANCE'
            quote_page_url = f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}"
            
            logger.info(f"Visiting quote page for {symbol}...")
            session.headers.update({
                "Referer": "https://www.nseindia.com/market-data/live-equity-market"
            })
            
            quote_resp = session.get(quote_page_url, timeout=30)
            quote_resp.raise_for_status()
            logger.info(f"Quote page status: {quote_resp.status_code}")
            
            # Add another delay
            time.sleep(random.uniform(1, 2))
            
            # Step 4: Update headers for API call
            session.headers.update({
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": quote_page_url,
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "X-Requested-With": "XMLHttpRequest"
            })
            
            logger.info(f"Fetching data from: {url}")
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            logger.info(f"API response status: {resp.status_code}")
            
            # Parse JSON response
            try:
                data = resp.json()
                logger.info("Successfully retrieved and parsed JSON data")
                return data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response content: {resp.text[:500]}...")
                return None

        except requests.exceptions.Timeout:
            logger.error("Request timed out")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Connection error occurred")
            return None
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 401:
                logger.error("401 Unauthorized - NSE API requires additional authentication")
                logger.error("This might be due to:")
                logger.error("1. Missing required cookies or tokens")
                logger.error("2. Rate limiting or IP blocking")
                logger.error("3. Changes in NSE's authentication mechanism")
                logger.error("Try accessing the website manually in a browser first")
            else:
                logger.error(f"HTTP error occurred: {e}")
                logger.error(f"Response status: {resp.status_code}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error occurred: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            return None
        
url = "https://www.nseindia.com/api/quote-equity?symbol=RELIANCE&section=trade_info"


scrip_code = "500325"
pe_url = f"https://api.bseindia.com/BseIndiaAPI/api/ComHeadernew/w?quotetype=EQ&scripcode={scrip_code}&seriesid="
mcap_url = f"https://api.bseindia.com/BseIndiaAPI/api/StockTrading/w?flag=&quotetype=EQ&scripcode={scrip_code}"
fifty_two_week_url = f"https://api.bseindia.com/BseIndiaAPI/api/HighLow/w?Type=EQ&flag=C&scripcode={scrip_code}"

nse_mcap_url = "https://www.nseindia.com/api/quote-equity?symbol=RELIANCE&section=trade_info"


def get_nse_mcap_data(url):
    data = get_nse_company_data(url)
    
    if data and isinstance(data, dict):
        try:
            # The response structure is: data -> marketDeptOrderBook -> tradeInfo -> totalMarketCap
            mcap = data["marketDeptOrderBook"]["tradeInfo"]["totalMarketCap"]
            logger.info(f"Successfully retrieved market cap: {mcap}")
            return mcap
            
        except KeyError as e:
            logger.error(f"KeyError: {e} - Data structure may have changed")
            logger.error("Available keys in response:")
            logger.error(f"Top level keys: {list(data.keys())}")
            
            # Try to show the actual structure for debugging
            if "marketDeptOrderBook" in data:
                logger.error(f"marketDeptOrderBook keys: {list(data['marketDeptOrderBook'].keys())}")
                if "tradeInfo" in data["marketDeptOrderBook"]:
                    logger.error(f"tradeInfo keys: {list(data['marketDeptOrderBook']['tradeInfo'].keys())}")
            
            return None
        except TypeError as e:
            logger.error(f"TypeError: {e} - Unexpected data type in response")
            return None
    else:
        logger.error("No valid data received from API")
        return None
    


result = get_nse_mcap_data(nse_mcap_url)
print(result)


