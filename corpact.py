import time
import json
import csv
from datetime import datetime, timezone
from urllib.parse import urlencode
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Optionally enable a simple persistent cache to avoid refetching unchanged data.
# pip install requests_cache
try:
    import requests_cache
    requests_cache.install_cache("bse_api_cache", expire_after=60)  # cache for 60s (adjust)
    CACHE_ENABLED = True
except Exception:
    CACHE_ENABLED = False

BASE_URL = "https://api.bseindia.com/BseIndiaAPI/api/DefaultData/w"

DEFAULT_HEADERS = {
    # Use a real browser-like UA; server may enforce.
    "User-Agent": "Mozilla/5.0 (compatible; DataScraper/1.0; +https://yourdomain.example)",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://www.bseindia.com",
    "Referer": "https://www.bseindia.com/",
}

# Create a requests.Session with retries and backoff
def create_session(max_retries=5, backoff_factor=0.5, status_forcelist=(500,502,503,504)):
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

def safe_get(session, url, params=None, timeout=30, respect_cache=True):
    """
    Safe GET wrapper:
     - uses session with retries
     - checks for caching hints in response headers
     - returns (response_json, response_headers)
    """
    # Construct full URL for logging
    full_url = url if params is None else f"{url}?{urlencode(params)}"
    for attempt in range(1, 6):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            # if requests_cache is active, resp.from_cache is available
            if hasattr(resp, "from_cache") and resp.from_cache:
                print(f"[CACHE] {full_url}")
            else:
                print(f"[FETCH] {full_url} -> {resp.status_code}")

            resp.raise_for_status()
            # parse JSON
            data = resp.json()
            return data, resp.headers
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", None)
            # 4xx errors are likely client errors; break out if permanent
            if code and 400 <= code < 500:
                print(f"[ERROR] HTTP {code} for {full_url}: giving up.")
                raise
            else:
                wait = attempt * 0.5
                print(f"[WARN] HTTP error, attempt {attempt}, sleeping {wait}s")
                time.sleep(wait)
        except requests.RequestException as e:
            wait = attempt * 0.5
            print(f"[WARN] network error on attempt {attempt}: {e}; sleeping {wait}s")
            time.sleep(wait)
    raise RuntimeError("Exceeded retries")

def parse_and_save_json(records, out_json_path="bse_data.json", out_csv_path=None):
    # Save JSON
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Saved JSON -> {out_json_path}")

    # Optionally save CSV if records is a list of dicts
    if out_csv_path and isinstance(records, list) and records:
        # Flatten keys (use keys of first element)
        keys = sorted(set().union(*(r.keys() for r in records)))
        with open(out_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for r in records:
                writer.writerow({k: r.get(k, "") for k in keys})
        print(f"Saved CSV -> {out_csv_path}")

def should_refetch(headers):
    """
    Decide whether to refetch based on cache headers.
    This is a simple heuristic: if Expires header in future, skip refetch.
    """
    expires = headers.get("Expires")
    cache_control = headers.get("Cache-Control", "")
    if expires:
        try:
            # HTTP date format
            expires_dt = datetime.strptime(expires, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
            if expires_dt > datetime.now(timezone.utc):
                return False
        except Exception:
            pass
    if "max-age" in cache_control:
        # server says how many seconds; we rely on requests_cache for this typically
        return False
    return True

def example_run():
    session = create_session()
    params = {
        "Fdate": "20251125",
        "Purposecode": "",
        "TDate": "20251201",
        "ddlcategorys": "E",
        "ddlindustrys": "",
        "scripcode": "",
        "segment": "0",
        "strSearch": "S",
    }

    data, headers = safe_get(session, BASE_URL, params=params)
    # The structure depends on API — adjust accordingly
    # Example expects a list in data.get("Table") or similar
    # We'll try several common places:
    if isinstance(data, dict):
        # many BSE endpoints put arrays under "Table" or "data"
        records = data.get("Table") or data.get("data") or data.get("Result") or data.get("response") or data
    else:
        records = data

    # If server response included cache hints and we have enough fresh cache, we could skip
    if not should_refetch(headers):
        print("[INFO] Server indicates this response is fresh for the short term.")

    # Save to files
    parse_and_save_json(records, out_json_path="bse_data.json", out_csv_path="bse_data.csv")

if __name__ == "__main__":
    example_run()
