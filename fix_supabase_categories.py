#!/usr/bin/env python3
"""
fix_supabase_categories.py

Script to fix categories in Supabase for rows that were already uploaded but had AI processing done later
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

try:
    from supabase import create_client, Client
except Exception:
    print("Supabase package not available")
    exit(1)

# Local DB path
LOCAL_DB_PATH = Path(__file__).parent / "data" / "bse_raw.db"

# Supabase env vars
SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_KEY2")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def get_supabase_client():
    if not SUPABASE_URL or not (SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY):
        print("Supabase credentials not found")
        return None
    
    key = SUPABASE_SERVICE_ROLE_KEY if SUPABASE_SERVICE_ROLE_KEY else SUPABASE_KEY
    try:
        client = create_client(SUPABASE_URL, key)
        print("Supabase client initialized")
        return client
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")
        return None

def fix_categories():
    if not LOCAL_DB_PATH.exists():
        print(f"Database not found at {LOCAL_DB_PATH}")
        return
    
    supabase = get_supabase_client()
    if not supabase:
        return
    
    conn = sqlite3.connect(str(LOCAL_DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    
    try:
        current_date = datetime.now().strftime('%Y-%m-%d')
        print(f"Checking for rows needing category update for date: {current_date}")
        
        cur = conn.cursor()
        
        # Find rows that are AI processed, sent to Supabase, but may need category update
        cur.execute("""
            SELECT corp_id, category, ai_summary, headline, sentiment, ai_processed, sent_to_supabase
            FROM corporatefilings 
            WHERE (date LIKE ? OR date = ?) 
            AND ai_processed = 1 
            AND sent_to_supabase = 1
            AND (category IS NOT NULL AND category != '' AND category != 'Error')
        """, (f"{current_date}%", current_date))
        
        rows = cur.fetchall()
        
        if not rows:
            print("No rows found needing category update")
            return
            
        print(f"Found {len(rows)} rows that may need category update in Supabase")
        
        for row in rows:
            corp_id = row["corp_id"]
            category = row["category"]
            ai_summary = row["ai_summary"]
            headline = row["headline"]
            sentiment = row["sentiment"]
            
            print(f"\\nUpdating corp_id: {corp_id}")
            print(f"  Category: {category}")
            print(f"  Has AI Summary: {'Yes' if ai_summary else 'No'}")
            
            try:
                # Check if row exists in Supabase first
                existing = supabase.table("corporatefilings").select("corp_id, category").eq("corp_id", corp_id).execute()
                
                if existing.data:
                    current_category = existing.data[0].get("category", "")
                    print(f"  Current Supabase category: '{current_category}'")
                    
                    # Update the row with AI processed data
                    update_payload = {
                        "category": category,
                        "ai_summary": ai_summary,
                        "headline": headline,
                        "sentiment": sentiment
                    }
                    
                    response = supabase.table("corporatefilings").update(update_payload).eq("corp_id", corp_id).execute()
                    print(f"  ✅ Successfully updated to category: '{category}'")
                else:
                    print(f"  ⚠️  Row not found in Supabase")
                    
            except Exception as e:
                print(f"  ❌ Failed to update: {e}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_categories()