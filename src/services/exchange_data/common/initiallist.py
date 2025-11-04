from supabase import create_client
import pandas as pd
import time
from dotenv import load_dotenv
import os
import requests
from io import StringIO

# Exchange segment (update as needed)
exchange_segments = ['BSE_EQ' , 'NSE_EQ']

for exchange_segment in exchange_segments:
    # API endpoint
    url = f'https://api.dhan.co/v2/instrument/{exchange_segment}'

    # Make the request
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        try:
            # Read CSV content from response.text
            df = pd.read_csv(StringIO(response.text), header=None)
            df.to_csv(f'{exchange_segment}_instruments.csv', index=False)
            print(f'Data saved to {exchange_segment}_instruments.csv')
        except Exception as e:
            print("Error parsing CSV:", e)
    else:
        print("Failed to fetch data:", response.status_code, response.text)

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_KEY2")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_all_table(table_name: str, batch_size: int = 1000, pause: float = 0.05):
    all_rows = []
    start = 0
    while True:
        end = start + batch_size - 1
        resp = supabase.table(table_name).select("*").range(start, end).execute()

        # ✅ In v2, resp is a dict-like object:
        rows = resp.data if hasattr(resp, "data") else resp.get("data", [])

        # In case of an error, supabase-py v2 raises exceptions, not resp.error
        if not rows:
            break

        all_rows.extend(rows)
        print(f"Fetched {len(rows)} rows (total {len(all_rows)})")

        if len(rows) < batch_size:
            break

        start += batch_size
        time.sleep(pause)
    return all_rows


table = "testtablenew"
rows = fetch_all_table(table)
df = pd.DataFrame(rows)
df.to_csv(f"{table}.csv", index=False)
print(f"✅ Saved {len(df)} rows to {table}.csv")