import os
import logging
import time
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- Load env ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
supabase_url = os.getenv("SUPABASE_URL2")
supabase_key = os.getenv("SUPABASE_KEY2")

# --- Supabase Client ---
supabase: Client = create_client(supabase_url, supabase_key)

# --- Sector list ---
list_of_sectors = [
    "IT Software & Services", "Hardware", "Telecom", "Fintech",
    "Banking", "Insurance", "Capital Markets", "Finance",
    "Healthcare Services", "Pharma & Biotech", "Medical Equipment",
    "Manufacturing", "Electrical Equipment", "Engineering", "Aerospace & Defense",
    "Metals & Mining", "Chemicals", "Construction Materials", "Paper & Forest",
    "Oil & Gas", "Power & Utilities", "Alternative Energy",
    "Food & Beverages", "Consumer Durables", "Personal Care", "Retail", "Textiles",
    "Automotive", "Transport Services", "Infrastructure",
    "Real Estate", "Construction",
    "Agriculture", "Fertilizers", "Commodities",
    "Media & Publishing", "Entertainment", "Diversified"
]

# --- Gemini Client ---
genai_client = genai.Client(api_key=GEMINI_API_KEY)

# --- Caching previously resolved sectors ---
sector_cache = {}

def get_sec(symbol):
    if symbol in sector_cache:
        return sector_cache[symbol]

    try:
        prompt = f"Which sector does the company {symbol} belong to among the {list_of_sectors}? If it belongs to multiple sectors then return Diversified. Just return the sector name and nothing else."
        response = genai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        for sec in list_of_sectors:
            if sec.lower() in response.text.lower():
                sector_cache[symbol] = sec
                return sec
    except Exception as e:
        logging.error(f"Gemini failed for {symbol}: {e}")
    
    return None

def fetch_all_stock_symbols():
    page_size = 1000
    all_records = []
    offset = 0

    while True:
        response = supabase.table('stocklistdata') \
            .select('symbol, sector') \
            .range(offset, offset + page_size - 1) \
            .execute()
        batch = response.data
        if not batch:
            break
        all_records.extend(batch)
        offset += page_size

    return all_records


def assign_sectors_to_all_companies():
    logging.info("🚀 Fetching all companies...")
    records = fetch_all_stock_symbols()

    symbols_to_process = [r["symbol"] for r in records if r.get("symbol") and not r.get("sector")]
    logging.info(f"🧠 Found {len(symbols_to_process)} companies needing sector assignment.")

    # --- Parallel Gemini Calls ---
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_symbol = {executor.submit(get_sec, symbol): symbol for symbol in symbols_to_process}
        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                sector = future.result()
                if sector:
                    results.append({"symbol": symbol, "sector": sector})
                    logging.info(f"✅ {symbol} -> {sector}")
                else:
                    logging.warning(f"❌ No sector found for {symbol}")
            except Exception as e:
                logging.error(f"Error resolving sector for {symbol}: {e}")

    logging.info(f"📦 Preparing batch update for {len(results)} companies...")

    # --- Batch Supabase Updates ---
    batch_size = 100
    for i in range(0, len(results), batch_size):
        batch = results[i:i+batch_size]
        for row in batch:
            try:
                supabase.table('stocklistdata') \
                    .update({"sector": row["sector"]}) \
                    .eq("symbol", row["symbol"]) \
                    .execute()
            except Exception as e:
                logging.error(f"🛑 Update failed for {row['symbol']}: {e}")

    logging.info("🎉 Sector assignment completed.")

if __name__ == "__main__":
    assign_sectors_to_all_companies()
