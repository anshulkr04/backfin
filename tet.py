import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime,date

# Load environment variables from .env file
load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL2')
SUPABASE_KEY = os.getenv('SUPABASE_KEY2')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def update_count(announcement):
    raw = announcement.get("date")
    today = datetime.fromisoformat(raw).date()
    category = announcement.get("category")

    # category is the column name, e.g. "Financial Results"
    # Increment logic: if row exists, increment; else start at 1

    # Step 1: Fetch today's row
    existing = (
        supabase
        .table("announcement_categories")
        .select("*")
        .eq("date", today)
        .maybe_single()
        .execute()
    )

    if existing.data is None:
        # No row for today, create a new one
        data = {"date": today, category: 1}
        response = supabase.table("announcement_categories").insert(data).execute()
    else:
        # Row exists; increment the category count
        current_value = existing.data.get(category, 0) or 0
        new_value = current_value + 1

        response = (
            supabase
            .table("announcement_categories")
            .update({category: new_value})
            .eq("date", today)
            .execute()
        )
        print(f"Updated {category} count to {new_value} for date {today}")

    return response
