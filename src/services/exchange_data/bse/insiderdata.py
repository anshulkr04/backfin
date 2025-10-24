
import os
import time
import glob
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException, JavascriptException
from webdriver_manager.chrome import ChromeDriverManager


# Set to True to run with visible Chrome (helpful for debugging)
DEBUG_NON_HEADLESS = False

def wait_for_download(folder, before_files, timeout=180):
    """
    Wait for a new file to appear in folder (not ending with .crdownload).
    Returns the full path to the downloaded file or None on timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        current_files = set(os.listdir(folder))
        new_files = current_files - before_files
        if new_files:
            for fname in new_files:
                # if it's a temporary partial file, skip until it finalizes
                if fname.endswith(".crdownload"):
                    continue
                return os.path.join(folder, fname)
        # also check for any file that was previously .crdownload but now finalized
        for f in os.listdir(folder):
            if f.endswith(".crdownload"):
                # still downloading; wait
                pass
        time.sleep(1.0)
    return None

def enable_chrome_downloads(driver, download_dir):
    """
    Use Chrome DevTools Protocol to allow downloads in headless mode.
    """
    try:
        # Selenium 4: use execute_cdp_cmd
        params = {"behavior": "allow", "downloadPath": download_dir}
        driver.execute_cdp_cmd("Page.setDownloadBehavior", params)
        return True
    except Exception as e:
        print("Warning: could not set download behavior via CDP:", e)
        return False

def main():
    url = "https://www.bseindia.com/corporates/Insider_Trading_new.aspx?expandable=2"
    download_dir = os.path.abspath(os.getcwd())

    chrome_options = Options()
    if not DEBUG_NON_HEADLESS:
        # headless new mode that supports downloads when CDP is used
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        print("Opening page:", url)
        driver.get(url)

        # Enable downloads through CDP (important for headless)
        ok = enable_chrome_downloads(driver, download_dir)
        if ok:
            print("Chrome download behavior enabled via CDP.")
        else:
            print("Proceeding without CDP download enable (may fail in headless).")

        wait = WebDriverWait(driver, 30)

        # Wait for presence of the download element
        try:
            download_btn = wait.until(EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_lnkDownload")))
            print("Found download element.")
        except TimeoutException:
            raise RuntimeError("Download element not present on page. The page might have changed or needs extra interaction.")

        # Try to wait until clickable (best-effort)
        try:
            download_btn = wait.until(EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_lnkDownload")))
            print("Element appears clickable.")
        except TimeoutException:
            print("Element not considered 'clickable' by Selenium; will attempt scroll + JS click fallback.")

        # Snapshot files before download for detection
        before_files = set(os.listdir(download_dir))
        print("Files before:", before_files)

        # Scroll element into view and attempt click
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", download_btn)
        time.sleep(0.5)

        clicked = False
        try:
            download_btn.click()
            clicked = True
            print("Clicked element normally.")
        except ElementClickInterceptedException:
            print("Normal click intercepted; attempting ActionChains click...")
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                ActionChains(driver).move_to_element(download_btn).click().perform()
                clicked = True
                print("ActionChains click succeeded.")
            except Exception as e:
                print("ActionChains failed:", e)
                print("Attempting JS click fallback...")
                try:
                    driver.execute_script("arguments[0].click();", download_btn)
                    clicked = True
                    print("JS click executed.")
                except JavascriptException as je:
                    print("JS click failed:", je)

        if not clicked:
            raise RuntimeError("Could not click the download element (all click attempts failed). Try DEBUG_NON_HEADLESS=True to debug visually.")

        # Wait for download to complete (increase timeout if slow)
        print("Waiting for download to appear in:", download_dir)
        downloaded_path = wait_for_download(download_dir, before_files, timeout=240)
        if downloaded_path is None:
            # give more debugging info: list current files and return
            print("Timeout waiting for downloaded file. Current files:", os.listdir(download_dir))
            raise RuntimeError("No new downloaded file detected in the download directory within timeout.")

        print("Detected downloaded file:", downloaded_path)

        # Move/rename to predictable filename
        final_name = os.path.join(download_dir, "insider_trading.csv")
        if os.path.exists(final_name):
            os.remove(final_name)
        shutil.move(downloaded_path, final_name)
        print("Moved and renamed to:", final_name)
        
        # Process and upload the downloaded CSV
        try:
            print("Starting post-download processing and upload...")
            run_post_processing_and_upload()
            print("Upload completed successfully!")
            
            # Clean up CSV files after successful upload
            cleanup_csv_files(download_dir)
            print("CSV files cleaned up successfully.")
            
        except Exception as e:
            print(f"Error during processing/upload: {e}")
            logging.exception("Error during processing/upload: %s", e)
            raise

    finally:
        driver.quit()


# ----------------- APPEND: post-download processing + upload to Supabase -----------------
import os
import pandas as pd
import numpy as np
from decimal import Decimal
from datetime import datetime
import logging

# Optional: load env from .env if you use that
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Paths and defaults
DOWNLOAD_CSV = os.path.join(os.getcwd(), "insider_trading.csv")
MAPPED_CSV = os.path.join(os.getcwd(), "insider_trading_bse_mapped.csv")

# Expected short columns (same as earlier)
EXPECTED_COLS = [
    "sec_code","sec_name","person_name","person_cat",
    "pre_sec_type","pre_sec_num","pre_sec_pct",
    "trans_sec_type","trans_sec_num","trans_value","trans_type",
    "post_sec_type","post_sec_num","post_sec_pct",
    "date_from","date_to","date_intimation","mode_acq",
    "exchange","symbol"
]

# --- Helper functions for mapping & parsing (re-usable) ---
def norm(s):
    if pd.isna(s):
        return ""
    return "".join(c.lower() for c in str(s).strip()).replace(" ", "").replace("_","")

# A comprehensive mapping heuristic for BSE column names
def build_col_map(headers):
    # Direct mapping for exact BSE column names (case-insensitive)
    exact_mappings = {
        "security code": "sec_code",
        "security name": "sec_name", 
        "name of person": "person_name",
        "category of person": "person_cat",
        "type of securities held prior to acquisition/disposed)": "pre_sec_type",
        "number of securities held prior to acquisition/disposed": "pre_sec_num",
        "%   of  securities held prior to acquisition/disposed": "pre_sec_pct",
        "type of securities Acquired/disposed/pledge etc.": "trans_sec_type",
        "number of securities acquired/disposed/pledge etc.": "trans_sec_num",
        "value  of securities acquired/disposed/pledge etc": "trans_value",
        "transaction type ( buy/sale/pledge/revoke/invoke)": "trans_type",
        "type of securities held post  acquisition/disposed/pledge  etc": "post_sec_type",
        "number of securities held post  acquisition/disposed/pledge etc": "post_sec_num",
        "post-transaction % of shareholding": "post_sec_pct",
        "date of acquisition of shares/sale of shares/date of allotment(from date)": "date_from",
        "date of acquisition of shares/sale of shares/date of allotment( to date  )": "date_to",
        "date of intimation to company": "date_intimation",
        "mode of acquisition": "mode_acq",
        "exchange on which the trade was executed": "exchange"
    }
    
    # Normalize headers for exact matching
    col_map = {}
    for header in headers:
        # Try exact match first (normalize spaces and case)
        normalized_header = " ".join(header.lower().strip().split())
        
        # Check for exact matches
        if normalized_header in exact_mappings:
            col_map[header] = exact_mappings[normalized_header]
            continue
            
        # Fallback to pattern matching for variations
        n = norm(header)
        mapped = None
        
        # Pattern-based matching for common variations
        if "securitycode" in n or "seccode" in n:
            mapped = "sec_code"
        elif "securityname" in n or "secname" in n:
            mapped = "sec_name"
        elif "nameofperson" in n:
            mapped = "person_name"
        elif "categoryofperson" in n:
            mapped = "person_cat"
        elif "typeofsecuritiesheldprior" in n:
            mapped = "pre_sec_type"
        elif "numberofsecuritiesheldprior" in n:
            mapped = "pre_sec_num"
        elif "%ofsecuritiesheldprior" in n or "percentofsecuritiesheldprior" in n:
            mapped = "pre_sec_pct"
        elif "typeofsecuritiesacquired" in n or "typeofsecuritiesdisposed" in n or "typeofsecuritiespledge" in n:
            mapped = "trans_sec_type"
        elif "numberofsecuritiesacquired" in n or "numberofsecuritiesdisposed" in n or "numberofsecuritiespledge" in n:
            mapped = "trans_sec_num"
        elif "valueofsecuritiesacquired" in n or "valueofsecuritiesdisposed" in n or "valueofsecuritiespledge" in n:
            mapped = "trans_value"
        elif "transactiontype" in n:
            mapped = "trans_type"
        elif "typeofsecuritiesheldpost" in n:
            mapped = "post_sec_type"
        elif "numberofsecuritiesheldpost" in n:
            mapped = "post_sec_num"
        elif "posttransaction" in n and ("%" in header or "percent" in n):
            mapped = "post_sec_pct"
        elif "dateofacquisition" in n and "fromdate" in n:
            mapped = "date_from"
        elif "dateofacquisition" in n and "todate" in n:
            mapped = "date_to"
        elif "dateofintimation" in n:
            mapped = "date_intimation"
        elif "modeofacquisition" in n:
            mapped = "mode_acq"
        elif "exchangeonwhich" in n or "tradewasexecuted" in n:
            mapped = "exchange"
        
        if mapped:
            col_map[header] = mapped
    
    return col_map

def is_bse_val(x):
    if pd.isna(x): return False
    s = str(x).upper()
    if "BSE" in s or "BOMBAY" in s or "BSE LTD" in s:
        return True
    parts = [p.strip() for p in s.replace("/",",").split(",")]
    return any(p.startswith("BSE") or p == "BSE" for p in parts)

def parse_int(x):
    if pd.isna(x): return None
    s = str(x).replace(",","").replace("—","").strip()
    if s in ("", "-", "NA", "N/A", "nan"): return None
    try:
        if "." in s:
            return int(float(s))
        return int(s)
    except Exception:
        import re
        m = re.search(r"(\d+)", s.replace(" ", ""))
        return int(m.group(1)) if m else None

def parse_decimal(x):
    if pd.isna(x): return None
    s = str(x).replace(",","").strip().replace("%","")
    if s in ("", "-", "NA", "N/A", "nan"): return None
    try:
        return Decimal(s)
    except Exception:
        try:
            return Decimal(str(float(s)))
        except Exception:
            return None

def parse_date(x):
    if pd.isna(x): return None
    s = str(x).strip()
    if s in ("", "-", "NA", "N/A", "nan"): return None
    formats = ("%Y-%m-%d","%d-%m-%Y","%d/%m/%Y","%Y/%m/%d","%d %b %Y","%d %B %Y","%Y.%m.%d","%d.%m.%Y","%b %d, %Y","%d %b, %Y")
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date().isoformat()
        except Exception:
            continue
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.date().isoformat()
    except Exception:
        return None

# --- Preprocess CSV into the mapped form and filter BSE ---
def preprocess_csv(inpath, outpath=None):
    if not os.path.exists(inpath):
        raise FileNotFoundError(f"CSV not found: {inpath}")
    # try reading with several delimiters like the prior code
    df = None
    for sep in [",",";","\t","|"]:
        try:
            tmp = pd.read_csv(inpath, sep=sep, engine="python")
            header_join = "".join([norm(h) for h in tmp.columns])
            if any(k in header_join for k in ["security","exchange","transaction"]):
                df = tmp
                break
        except Exception:
            pass
    if df is None:
        df = pd.read_csv(inpath, engine="python", encoding="latin1")

    headers = list(df.columns)
    logging.info("Detected CSV columns: %s", headers)
    col_map = build_col_map(headers)
    logging.info("Column mapping results:")
    for orig, mapped in col_map.items():
        logging.info("  '%s' -> '%s'", orig, mapped)
    
    # Check for unmapped critical columns
    mapped_cols = set(col_map.values())
    critical_cols = {'sec_code', 'sec_name', 'person_name', 'trans_sec_num', 'trans_value'}
    missing_critical = critical_cols - mapped_cols
    if missing_critical:
        logging.warning("Missing critical column mappings: %s", missing_critical)

    out = pd.DataFrame(columns=EXPECTED_COLS)
    
    # Apply column mappings
    for src, dst in col_map.items():
        if src in df.columns:
            out[dst] = df[src]
            logging.info("Mapped column '%s' to '%s' with %d non-null values", src, dst, df[src].notna().sum())
    
    # Fallback attempts for missing critical columns
    if out["person_name"].isna().all() or "person_name" not in col_map.values():
        logging.warning("person_name column not mapped, trying fallback detection")
        for c in headers:
            c_norm = norm(c)
            if "person" in c_norm or ("name" in c_norm and "security" not in c_norm and "company" not in c_norm):
                out["person_name"] = df[c]
                logging.info("Fallback: mapped '%s' to person_name", c)
                break
    
    # Additional fallbacks for other critical fields
    if out["sec_code"].isna().all() or "sec_code" not in col_map.values():
        for c in headers:
            if "code" in norm(c) and "security" in norm(c).lower():
                out["sec_code"] = df[c]
                logging.info("Fallback: mapped '%s' to sec_code", c)
                break
    
    if out["trans_sec_num"].isna().all() or "trans_sec_num" not in col_map.values():
        for c in headers:
            c_norm = norm(c)
            if "number" in c_norm and ("acquired" in c_norm or "disposed" in c_norm or "pledge" in c_norm):
                out["trans_sec_num"] = df[c]
                logging.info("Fallback: mapped '%s' to trans_sec_num", c)
                break

    out = out.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    # normalize & filter
    out["exchange_norm"] = out["exchange"].fillna("").apply(is_bse_val)
    filtered = out[out["exchange_norm"] == True].copy()
    filtered.drop(columns=["exchange_norm"], inplace=True)

    # coerce numeric fields
    for col in ["pre_sec_num","trans_sec_num","post_sec_num"]:
        if col in filtered.columns:
            filtered[col] = filtered[col].apply(parse_int)

    for col in ["pre_sec_pct","post_sec_pct","trans_value"]:
        if col in filtered.columns:
            filtered[col] = filtered[col].apply(parse_decimal)

    for dcol in ["date_from","date_to","date_intimation"]:
        if dcol in filtered.columns:
            filtered[dcol] = filtered[dcol].apply(parse_date)
    
    # Set exchange to "BSE" for all records since this is BSE data
    filtered['exchange'] = 'BSE'
    logging.info("Set exchange column to 'BSE' for all records")
    
    # Initialize symbol column as None - database trigger will populate symbol from stocklistdata using sec_code
    filtered['symbol'] = None
    logging.info("Initialized symbol column as None - database trigger will populate symbol from stocklistdata using sec_code")

    filtered = filtered[EXPECTED_COLS]
    
    # Log data quality summary
    logging.info("Data quality summary after preprocessing:")
    for col in EXPECTED_COLS:
        non_null_count = filtered[col].notna().sum()
        total_count = len(filtered)
        logging.info("  %s: %d/%d non-null values (%.1f%%)", col, non_null_count, total_count, 
                    (non_null_count/total_count*100) if total_count > 0 else 0)
    
    if outpath:
        filtered.to_csv(outpath, index=False)
        logging.info("Saved preprocessed data to: %s", outpath)
    
    logging.info("Preprocessing complete: %d rows after filtering for BSE", len(filtered))
    return filtered


def upload_via_supabase_client(df, supabase_url, supabase_key, batch=100):
    logging.info("Uploading via Supabase client to %s", supabase_url)
    from supabase import create_client
    import math
    supabase = create_client(supabase_url, supabase_key)
    
    # Convert Decimal objects to float and handle NaN values for JSON serialization
    df_serializable = df.copy()
    for col in df_serializable.columns:
        if df_serializable[col].dtype == 'object':
            df_serializable[col] = df_serializable[col].apply(
                lambda x: float(x) if isinstance(x, Decimal) else x
            )
    
    # Replace NaN values with None (which becomes null in JSON)
    df_serializable = df_serializable.replace({float('nan'): None})
    
    # Also handle any remaining NaN values using numpy
    df_serializable = df_serializable.where(pd.notnull(df_serializable), None)
    
    # Truncate string fields to match database schema limits
    field_limits = {
        'sec_code': 20,
        'sec_name': 255,
        'person_name': 255,
        'person_cat': 50,
        'pre_sec_type': 50,
        'trans_sec_type': 50,
        'trans_type': 20,
        'post_sec_type': 50,
        'mode_acq': 50,
        'exchange': 50,
        'symbol': 50
    }
    
    for col, max_length in field_limits.items():
        if col in df_serializable.columns:
            df_serializable[col] = df_serializable[col].apply(
                lambda x: str(x)[:max_length] if x is not None and isinstance(x, str) and len(str(x)) > max_length else x
            )
    
    # Convert to records for upload
    records = df_serializable.to_dict(orient="records")
    
    # Final cleanup: ensure no NaN values remain
    for record in records:
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                record[key] = None
    
    # Log sample record for debugging
    if records:
        logging.info("Sample record: %s", records[0])
        logging.info("Total records to upload: %d", len(records))
    
    for i in range(0, len(records), batch):
        chunk = records[i:i+batch]
        try:
            res = supabase.table("insider_trading").insert(chunk).execute()
            # res may be a dict-like response; we log returned value
            logging.info("Supabase client inserted batch %d - %d, response: %s", i, i+len(chunk)-1, getattr(res, 'status_code', str(res)))
        except Exception as e:
            logging.error("Error inserting batch %d - %d: %s", i, i+len(chunk)-1, e)
            # Log the problematic chunk for debugging
            logging.error("Problematic chunk: %s", chunk[:2])  # Log first 2 records of the failed chunk
            raise
    logging.info("Supabase client upload finished.")

def cleanup_csv_files(download_dir):
    """Clean up downloaded and processed CSV files"""
    files_to_delete = [
        os.path.join(download_dir, "insider_trading.csv"),
        os.path.join(download_dir, "insider_trading_bse_mapped.csv")
    ]
    
    for file_path in files_to_delete:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted: {file_path}")
                logging.info("Deleted file: %s", file_path)
        except Exception as e:
            print(f"Warning: Could not delete {file_path}: {e}")
            logging.warning("Could not delete file %s: %s", file_path, e)

def ensure_and_upload(df):
    supabase_url = os.environ.get("SUPABASE_URL2")
    supabase_key = os.environ.get("SUPABASE_KEY2")
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY environment variables are required.")
    upload_via_supabase_client(df, supabase_url, supabase_key, batch=100)

# --- Integrate into your main flow: call this after download and rename step ---
def run_post_processing_and_upload():
    logging.info("Starting post-download preprocessing and upload.")
    df = preprocess_csv(DOWNLOAD_CSV, outpath=MAPPED_CSV)
    if df.empty:
        logging.warning("No rows after filtering for BSE. Nothing to upload.")
        return
    ensure_and_upload(df)
    logging.info("All done. Mapped CSV saved at: %s", MAPPED_CSV)

# If this script is run directly, run the complete flow: download, process, upload, and cleanup
if __name__ == "__main__":
    try:
        # Run the main download function which now includes processing, upload, and cleanup
        main()
    except Exception as exc:
        logging.exception("Error during complete flow: %s", exc)
        raise

