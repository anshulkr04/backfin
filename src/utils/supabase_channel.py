import re
from supabase import create_client, Client
from typing import Optional
import time
from dotenv import load_dotenv
import os

load_dotenv()


# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL2") # Replace with your actual Supabase URL
SUPABASE_KEY = os.getenv("SUPABASE_KEY2")  # Replace with your actual Supabase anon key

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

item_type = "FINANCIAL_RESULT"
if(item_type == "LARGE_DEAL"):
    item_cell = "related_deal_id"
else:
    item_cell = "related_announcement_id"

data = {
    "user_id" : "0a6cb215-69f4-457c-b5ab-5f1dcadcd013",
    "item_type": item_type,
    item_cell : "0005aca5-07bd-4c56-9ff2-c10d4230abaf",
    "note": "finanacial",
}
isin = "INE121E01018"
response = (
    supabase.table("stockpricedata")
    .select("*")
    .eq("isin", isin)
    .order("date", desc=True)
    .limit(1)
    .execute()
)
data = response.data[0]
price = data.get("close")
print(price)