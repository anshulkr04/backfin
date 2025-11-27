#!/usr/bin/env python3
"""
Safe scraper for:
https://www.nseindia.com/api/corporates-corporateActions?index=equities&from_date=24-11-2025&to_date=25-11-2025

Behavior:
- Performs an initial GET to https://www.nseindia.com to obtain cookies/headers.
- Calls API with appropriate headers.
- Handles gzip and brotli (br) response decoding.
- Uses retries + backoff (urllib3 Retry).
- Does NOT use caching or write sqlite files.
"""

import time
import json
from urllib.parse import urlencode
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Optional: brotli is required to decode 'br' content encoding.
# pip install brotli
try:
    import brotli  # type: ignore
    _HAS_BROTLI = True
except Exception:
    brotli = None
    _HAS_BROTLI = False

# --- Config ---
BASE_URL = "https://www.nseindia.com/api/corporates-corporateActions"
HOMEPAGE = "https://www.nseindia.com/"

DEFAULT_HEADERS = {
    # Browser-like UA reduces risk of 403 from NSE
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    # Accept everything; server responds with application/json
    "Accept": "*/*",
    # Indicate we accept Brotli and gzip.
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-actions",
}

# Retry/backoff settings
RETRY_TOTAL = 5
BACKOFF_FACTOR = 0.6
STATUS_FORCELIST = (429, 500, 502, 503, 504)  # 429 too many requests is retryable here


# --- Utilities ---
def create_session(max_retries=RETRY_TOTAL, backoff_factor=BACKOFF_FACTOR):
    sess = requests.Session()
    # Set browser-like headers on session (will be used for initial homepage request too)
    sess.headers.update(DEFAULT_HEADERS)

    retry = Retry(
        total=max_retries,
        read=max_retries,
        connect=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=STATUS_FORCELIST,
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess


def decode_response_content(resp):
    """
    Decode response content honoring Content-Encoding.
    Supports gzip (requests auto-decodes) and brotli ('br') if brotli library present.
    If brotli is not installed and content-encoding contains 'br', raise helpful error.
    """
    enc = (resp.headers.get("Content-Encoding") or resp.headers.get("content-encoding") or "").lower()
    if "br" in enc:
        if not _HAS_BROTLI:
            raise RuntimeError(
                "Response uses Brotli (br) encoding but 'brotli' python package is not installed. "
                "Install it with: pip install brotli"
            )
        # resp.content is bytes; requests doesn't auto-decode br
        try:
            return brotli.decompress(resp.content).decode(resp.encoding or "utf-8")
        except Exception as e:
            # Fallback: try to use resp.text if brotli decompression fails
            # Sometimes the content is already decompressed or the header is incorrect
            print(f"[WARN] Brotli decompression failed: {e}. Trying fallback to resp.text")
            try:
                return resp.text
            except Exception as e2:
                raise RuntimeError(f"Failed to decompress brotli content: {e}, fallback also failed: {e2}")
    else:
        # For gzip/deflate requests usually auto-decodes and resp.text is fine
        return resp.text


# --- Main fetch flow ---
def fetch_nse_corporate_actions(from_date: str, to_date: str, index: str = "equities", timeout: int = 30):
    """
    Fetch corporate actions from NSE between from_date and to_date.
    Date format used by NSE: DD-MM-YYYY -> e.g. "24-11-2025"

    Returns: parsed JSON (python object), response headers
    """
    session = create_session()

    # 1) initial visit to homepage to obtain cookies / session parameters (important for NSE)
    try:
        print(f"[{datetime.utcnow().isoformat()}] Visiting NSE homepage to obtain cookies...")
        r_home = session.get(HOMEPAGE, timeout=15)
        # allow the retry adapter to handle transient errors; but if homepage returns a 4xx/5xx, raise
        r_home.raise_for_status()
        print(f"[INFO] Got homepage cookies: {dict(session.cookies)}")
        # small polite pause to mimic real browser behaviour
        time.sleep(0.3)
    except requests.RequestException as e:
        # Some environments may still work without initial cookies — but warn strongly.
        print(f"[WARN] Failed to fetch NSE homepage: {e}. Continuing anyway; you may get 403 if site blocks requests.")

    # 2) Construct API params & headers (add/update Referer & any other required header)
    params = {"index": index, "from_date": from_date, "to_date": to_date}
    # Ensure Referer is set (some NSE endpoints check it)
    session.headers.update({"Referer": DEFAULT_HEADERS["Referer"], "Origin": "https://www.nseindia.com"})

    # 3) Perform GET on API endpoint (retries are handled by the session adapter)
    try:
        print(f"[{datetime.utcnow().isoformat()}] Requesting API {BASE_URL} with params {params}")
        resp = session.get(BASE_URL, params=params, timeout=timeout)
        print(f"[{datetime.utcnow().isoformat()}] Response: {resp.status_code}")
        # If 403/401: show helpful diagnostic
        if resp.status_code in (401, 403):
            raise RuntimeError(
                f"Server returned {resp.status_code}. NSE often blocks requests without proper session cookies or "
                "anti-bot headers. Ensure you visited the homepage and have required cookies; consider adding small delays."
            )
        resp.raise_for_status()

        body_text = decode_response_content(resp)
        data = json.loads(body_text)
        return data, resp.headers

    except requests.RequestException as e:
        raise RuntimeError(f"Network/HTTP error while fetching NSE API: {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON response: {e}")

# --- Example usage ---
if __name__ == "__main__":
    # Example date range (from your request)
    FROM = "24-11-2025"
    TO = "25-11-2025"

    try:
        records, headers = fetch_nse_corporate_actions(FROM, TO)
        # Option: print summary or store in memory; no file writes by default
        if isinstance(records, list):
            print(f"[INFO] Retrieved {len(records)} records.")
        else:
            # likely a dict with keys
            print(f"[INFO] Retrieved object with keys: {list(records.keys()) if isinstance(records, dict) else type(records)}")
        # Pretty-print first item (if list) — safe for large responses, only shows one element
        if isinstance(records, list) and records:
            print("[SAMPLE RECORD]", json.dumps(records[0], indent=2))
    except Exception as e:
        print("[ERROR]", e)
