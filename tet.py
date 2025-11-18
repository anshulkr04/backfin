import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime,date
import json
import time
from google import genai

# Load environment variables from .env file
load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL2')
SUPABASE_KEY = os.getenv('SUPABASE_KEY2')

def get_supabase_client():
    """Create a fresh Supabase client"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = get_supabase_client()


# def update_count(announcement, client, max_retries=3):
#     """Update count with retry logic and error handling"""
#     raw = announcement.get("date")
#     # Convert to date object for processing
#     date_obj = datetime.fromisoformat(raw).date()
#     # Convert back to ISO string for Supabase
#     today = date_obj.isoformat()
#     category = announcement.get("category")

#     # category is the column name, e.g. "Financial Results"
#     # Increment logic: if row exists, increment; else start at 1

#     for attempt in range(max_retries):
#         try:
#             # Step 1: Fetch today's row
#             existing = (
#                 client
#                 .table("announcement_categories")
#                 .select("*")
#                 .eq("date", today)
#                 .maybe_single()
#                 .execute()
#             )

#             if existing is None:
#                 # No row for today, create a new one
#                 data = {"date": today, category: 1}
#                 response = client.table("announcement_categories").insert(data).execute()
#                 print(f"Created new row for date {today} with {category}=1")
#             else:
#                 # Row exists; increment the category count
#                 current_value = existing.data.get(category, 0) or 0
#                 new_value = current_value + 1

#                 response = (
#                     client
#                     .table("announcement_categories")
#                     .update({category: new_value})
#                     .eq("date", today)
#                     .execute()
#                 )
#                 print(f"Updated {category} count to {new_value} for date {today}")

#             return response
            
#         except Exception as e:
#             if attempt < max_retries - 1:
#                 print(f"Error on attempt {attempt + 1}: {e}. Retrying...")
#                 time.sleep(1)  # Wait before retry
#                 # Get a fresh client for retry
#                 client = get_supabase_client()
#             else:
#                 print(f"Failed after {max_retries} attempts: {e}")
#                 raise

# with open("tet.json" , "r") as file:
#     data = json.load(file)

# print(f"Processing {len(data)} announcements...")

# # Process in batches to avoid connection exhaustion
# batch_size = 100
# total_processed = 0
# failed_count = 0

# for i in range(0, len(data), batch_size):
#     batch = data[i:i + batch_size]
    
#     # Get a fresh client for each batch
#     client = get_supabase_client()
    
#     print(f"\nProcessing batch {i//batch_size + 1} ({i+1}-{min(i+batch_size, len(data))} of {len(data)})")
    
#     for announcement in batch:
#         try:
#             update_count(announcement, client)
#             total_processed += 1
            
#             # Small delay to avoid overwhelming the connection
#             if total_processed % 10 == 0:
#                 time.sleep(0.1)
                
#         except Exception as e:
#             print(f"Failed to process announcement: {e}")
#             failed_count += 1
#             continue
    
#     # Longer pause between batches
#     if i + batch_size < len(data):
#         print(f"Batch complete. Pausing for 2 seconds...")
#         time.sleep(2)

# print(f"\n{'='*50}")
# print(f"Processing complete!")
# print(f"Total processed: {total_processed}")
# print(f"Failed: {failed_count}")
# print(f"Success rate: {(total_processed/(total_processed+failed_count)*100):.2f}%")


gemini_api = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=gemini_api)

myfile = client.files.upload(file="./back.pdf")


response = client.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents=["Explain the contents of this file", myfile],
)

print(response.text)

