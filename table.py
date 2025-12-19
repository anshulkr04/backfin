from supabase import create_client
import csv
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_KEY2")


TABLE_NAME = "corporatefilings"
OUTPUT_FILE = "corporatefilings_after_2025-09-01.csv"

# Inclusive start date: all rows where date >= this string
START_DATE = "2025-09-01"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

page = 0
limit = 3000
total_rows = 0
wrote_header = False

while True:
    start = page * limit
    end = start + limit - 1

    # Filter by date and paginate
    res = (
        supabase
        .table(TABLE_NAME)
        .select("*")
        .gte("date", START_DATE)           # only filings on/after 2025-09-01
        .order("date", desc=False)         # stable order for paging
        .range(start, end)
        .execute()
    )

    rows = res.data

    if not rows:
        break  # no more data

    # Append to CSV as we go (no need to keep all rows in memory)
    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        if not wrote_header:
            writer.writeheader()
            wrote_header = True
        writer.writerows(rows)

    batch_count = len(rows)
    total_rows += batch_count
    print(f"Fetched {batch_count} rows in page {page}, total so far: {total_rows}")

    # If we got fewer than limit rows, it's the last page
    if batch_count < limit:
        break

    page += 1

print(f"Done! Total rows written: {total_rows}")
print(f"Saved to: {OUTPUT_FILE}")
