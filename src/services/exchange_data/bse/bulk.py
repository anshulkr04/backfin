from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from supabase import create_client
import os
import json
import re
from dotenv import load_dotenv
load_dotenv()

# ---------- Helpers ----------
def convert_to_json(data):
    headers = data[0]
    rows = data[1:]
    return [dict(zip(headers, row)) for row in rows]

def parse_date_ddmmyyyy(s):
    # e.g. "23/10/2025" -> "2025-10-23"
    return datetime.strptime(s, "%d/%m/%Y").date().isoformat()

def parse_int(s):
    # "300,000" -> 300000
    return int(re.sub(r"[^\d]", "", s)) if s else None

def parse_price_to_4dp(s):
    # "88.16" -> Decimal with 4 dp
    if s is None or s == "":
        return None
    d = Decimal(re.sub(r"[^\d.]", "", s))
    return d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

def bse_row_to_supabase(row):
    # Convert Deal Type (B -> BUY, S -> SELL)
    deal_type_raw = (row.get("Deal Type *") or "").strip().upper()
    if deal_type_raw == "B":
        deal_type = "BUY"
    elif deal_type_raw == "S":
        deal_type = "SELL"
    else:
        deal_type = None

    # Security Code -> securityid
    security_code = (row.get("Security Code") or "").strip() or None

    return {
        "symbol": row.get("Security Name") or None,        # Security Name = symbol
        "securityid": security_code,                       # Security Code
        "date": parse_date_ddmmyyyy(row.get("Deal Date", "")),
        "client_name": row.get("Client Name") or None,
        "deal_type": deal_type,
        "quantity": parse_int(row.get("Quantity", "")),
        "price": str(parse_price_to_4dp(row.get("Price **", ""))) if parse_price_to_4dp(row.get("Price **", "")) is not None else None,
        "exchange": "BSE",
        "deal": "BULK",                                    # new column → always BULK for this scraper
    }

# ---------- Scrape ----------
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=chrome_options)

try:
    driver.get("https://www.bseindia.com/markets/equity/EQReports/bulk_deals.aspx")

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_gvbulk_deals"))
    )
    table = driver.find_element(By.ID, "ContentPlaceHolder1_gvbulk_deals")
    rows = table.find_elements(By.TAG_NAME, "tr")

    data = []
    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "th") + row.find_elements(By.TAG_NAME, "td")
        data.append([cell.text.strip() for cell in cells])

    json_data = convert_to_json(data)

    # Transform to Supabase rows
    records = [bse_row_to_supabase(r) for r in json_data]

    # (Optional) filter out any header/empty artifacts just in case
    records = [
        rec for rec in records
        if rec["symbol"] and rec["date"] and rec["deal_type"] and rec["quantity"] is not None and rec["price"] is not None
    ]

    print(f"Prepared {len(records)} record(s) for insert.")
finally:
    driver.quit()

# ---------- Supabase Insert ----------
SUPABASE_URL = os.environ.get("SUPABASE_URL2")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY2")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_*_KEY environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

if records:
    resp = supabase.table("deals").insert(records).execute()
    print("Insert done.")
    try:
        print("Inserted rows:", len(resp.data) if resp and getattr(resp, "data", None) else "unknown")
    except Exception:
        pass
else:
    print("No valid records to insert.")
