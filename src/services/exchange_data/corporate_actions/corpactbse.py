#!/usr/bin/env python3
"""
Clean, robust scraper for the BSE endpoint (no caching, no CSV).
Saves JSON output to file or returns parsed data.
"""
import time
import json
from datetime import datetime, timezone
from urllib.parse import urlencode
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://api.bseindia.com/BseIndiaAPI/api/DefaultData/w"

DEFAULT_HEADERS = {
    # Browser-like UA to reduce risk of server blocking
    "User-Agent": "Mozilla/5.0 (compatible; DataScraper/1.0; +https://example.local)",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://www.bseindia.com",
    "Referer": "https://www.bseindia.com/",
}

def create_session(max_retries=5, backoff_factor=0.5, status_forcelist=(500,502,503,504)):
    """Create a requests.Session with retry/backoff and connection pooling."""
    session = requests.Session()
    retry = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(DEFAULT_HEADERS)
    return session

def safe_get(session, url, params=None, timeout=30, max_attempts=5):
    """
    Perform a safe GET with retries and exponential-ish backoff.
    Returns (parsed_json, response_headers).
    Raises on fatal HTTP 4xx or after retries exhausted.
    """
    full_url = url if params is None else f"{url}?{urlencode(params)}"
    attempt = 0
    while attempt < max_attempts:
        try:
            resp = session.get(url, params=params, timeout=timeout)
            # logging
            print(f"[{datetime.utcnow().isoformat()}] GET {full_url} -> {resp.status_code}")
            # Non-retryable client errors
            if 400 <= resp.status_code < 500:
                resp.raise_for_status()
            resp.raise_for_status()
            return resp.json(), resp.headers
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", None)
            # Give up on 4xx; retry on 5xx
            if code and 400 <= code < 500:
                print(f"[ERROR] HTTP {code} for {full_url} — not retrying.")
                raise
            attempt += 1
            wait = attempt * 0.6
            print(f"[WARN] HTTP error (status {code}), attempt {attempt}/{max_attempts}. Sleeping {wait:.1f}s")
            time.sleep(wait)
        except requests.RequestException as e:
            attempt += 1
            wait = attempt * 0.6
            print(f"[WARN] Network error: {e}. Attempt {attempt}/{max_attempts}. Sleeping {wait:.1f}s")
            time.sleep(wait)
    raise RuntimeError(f"Failed to fetch {full_url} after {max_attempts} attempts")

def parse_response_json(data):
    """
    Convert API response to the primary records object.
    Adjust this depending on actual API shape.
    Common BSE shapes: {"Table": [...]} or top-level list/dict.
    """
    if isinstance(data, dict):
        for key in ("Table", "data", "Result", "response", "Records"):
            if key in data:
                return data[key]
        return data  # fall back to entire object
    return data

def save_json(records, out_path="bse_data.json"):
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Saved JSON -> {out_path}")

def fetch_bse(Fdate="20251125", TDate="20251201", ddlcategorys="E", strSearch="S"):
    """
    Example wrapper: fetch using the parameters you supplied earlier.
    Returns parsed records and headers.
    """
    session = create_session()
    params = {
        "Fdate": Fdate,
        "Purposecode": "",
        "TDate": TDate,
        "ddlcategorys": ddlcategorys,
        "ddlindustrys": "",
        "scripcode": "",
        "segment": "0",
        "strSearch": strSearch,
    }
    data, headers = safe_get(session, BASE_URL, params=params)
    records = parse_response_json(data)
    return records, headers

if __name__ == "__main__":
    # example usage
    records, headers = fetch_bse()
    # either save or process programmatically
    save_json(records, out_path="bse_data.json")
    # if you prefer not to save, just print a short summary:
    if isinstance(records, list):
        print(f"[INFO] Retrieved {len(records)} records.")
    else:
        print(f"[INFO] Retrieved object type: {type(records)}")
