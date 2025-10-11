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
        
def get_nse_company_data(url_array):
    """
    Fetch NSE company data from multiple API URLs using a single session.
    
    Args:
        url_array (list): List of NSE API URLs to fetch data from
        
    Returns:
        dict: Dictionary mapping URLs to their JSON response data.
              Failed requests will have None as their value.
    """
    if not url_array or not isinstance(url_array, list):
        logger.error("url_array must be a non-empty list")
        return {}
    
    results = {}
    
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

        logger.info(f"Initializing session for {len(url_array)} URLs...")
        
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
            
            # Step 3: Visit equity quotes page (general page that covers all symbols)
            logger.info("Visiting equity quotes page...")
            session.headers.update({
                "Referer": "https://www.nseindia.com/market-data/live-equity-market"
            })
            
            quotes_resp = session.get("https://www.nseindia.com/get-quotes/equity", timeout=30)
            quotes_resp.raise_for_status()
            logger.info(f"Equity quotes page status: {quotes_resp.status_code}")
            
            # Add another delay
            time.sleep(random.uniform(1, 2))
            
            # Step 4: Update headers for API calls
            session.headers.update({
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://www.nseindia.com/get-quotes/equity",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "X-Requested-With": "XMLHttpRequest"
            })
            
            logger.info("Session established successfully. Starting batch API calls...")
            
            # Step 5: Fetch data from all URLs
            for i, url in enumerate(url_array, 1):
                logger.info(f"Fetching data from URL {i}/{len(url_array)}: {url}")
                
                try:
                    # Extract symbol for logging
                    symbol = url.split('symbol=')[1].split('&')[0] if 'symbol=' in url else 'Unknown'
                    logger.info(f"Processing symbol: {symbol}")
                    
                    resp = session.get(url, timeout=30)
                    resp.raise_for_status()
                    logger.info(f"API response status for {symbol}: {resp.status_code}")
                    
                    # Parse JSON response
                    try:
                        data = resp.json()
                        results[url] = data
                        logger.info(f"Successfully retrieved data for {symbol}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON for {symbol}: {e}")
                        results[url] = None
                
                except requests.exceptions.HTTPError as e:
                    logger.error(f"HTTP error for {symbol}: {e}")
                    if hasattr(e.response, 'status_code'):
                        logger.error(f"Status code: {e.response.status_code}")
                    results[url] = None
                
                except requests.exceptions.RequestException as e:
                    logger.error(f"Request error for {symbol}: {e}")
                    results[url] = None
                
                except Exception as e:
                    logger.error(f"Unexpected error for {symbol}: {e}")
                    results[url] = None
                
                # Add small delay between API calls to avoid overwhelming the server
                if i < len(url_array):  # Don't delay after the last request
                    time.sleep(random.uniform(0.5, 1.5))

        except requests.exceptions.Timeout:
            logger.error("Session initialization timed out")
            return {}
        except requests.exceptions.ConnectionError:
            logger.error("Connection error during session initialization")
            return {}
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error during session initialization: {e}")
            return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during session initialization: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error during session initialization: {e}")
            return {}
    
    success_count = sum(1 for result in results.values() if result is not None)
    logger.info(f"Batch processing completed. Successfully fetched {success_count}/{len(url_array)} URLs")
    
    return results
        
url = "https://www.nseindia.com/api/quote-equity?symbol=RELIANCE&section=trade_info"


scrip_code = "500325"
pe_url = f"https://api.bseindia.com/BseIndiaAPI/api/ComHeadernew/w?quotetype=EQ&scripcode={scrip_code}&seriesid="
mcap_url = f"https://api.bseindia.com/BseIndiaAPI/api/StockTrading/w?flag=&quotetype=EQ&scripcode={scrip_code}"
fifty_two_week_url = f"https://api.bseindia.com/BseIndiaAPI/api/HighLow/w?Type=EQ&flag=C&scripcode={scrip_code}"

nse_mcap_url = "https://www.nseindia.com/api/quote-equity?symbol=RELIANCE&section=trade_info"
nse_com_url = "https://www.nseindia.com/api/quote-equity?symbol=RELIANCE"

nse_url_array = [nse_com_url, nse_mcap_url]

data = get_nse_company_data(nse_url_array)
print(data)


# def get_nse_mcap_data(url):
#     data = get_nse_company_data(url)
    
#     if data and isinstance(data, dict):
#         try:
#             # The response structure is: data -> marketDeptOrderBook -> tradeInfo -> totalMarketCap
#             mcap = data["marketDeptOrderBook"]["tradeInfo"]["totalMarketCap"]
#             logger.info(f"Successfully retrieved market cap: {mcap}")
#             return mcap
            
#         except KeyError as e:
#             logger.error(f"KeyError: {e} - Data structure may have changed")
#             logger.error("Available keys in response:")
#             logger.error(f"Top level keys: {list(data.keys())}")
            
#             # Try to show the actual structure for debugging
#             if "marketDeptOrderBook" in data:
#                 logger.error(f"marketDeptOrderBook keys: {list(data['marketDeptOrderBook'].keys())}")
#                 if "tradeInfo" in data["marketDeptOrderBook"]:
#                     logger.error(f"tradeInfo keys: {list(data['marketDeptOrderBook']['tradeInfo'].keys())}")
            
#             return None
#         except TypeError as e:
#             logger.error(f"TypeError: {e} - Unexpected data type in response")
#             return None
#     else:
#         logger.error("No valid data received from API")
#         return None
    


# result = get_nse_mcap_data(nse_mcap_url)
# print(result)


