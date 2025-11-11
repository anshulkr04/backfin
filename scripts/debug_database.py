#!/usr/bin/env python3
"""
debug_db.py

Quick script to check the state of corporatefilings table for today's date
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime

# Local DB path
LOCAL_DB_PATH = Path(__file__).parent / "data" / "bse_raw.db"

def check_db_state():
    if not LOCAL_DB_PATH.exists():
        print(f"Database not found at {LOCAL_DB_PATH}")
        return
    
    conn = sqlite3.connect(str(LOCAL_DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    
    try:
        current_date = datetime.now().strftime('%Y-%m-%d')
        print(f"Checking corporatefilings for date: {current_date}")
        
        cur = conn.cursor()
        
        # Get all rows for today
        cur.execute("""
            SELECT corp_id, ai_processed, sent_to_supabase, category, ai_summary, summary 
            FROM corporatefilings 
            WHERE date LIKE ? OR date = ?
            ORDER BY corp_id
        """, (f"{current_date}%", current_date))
        
        rows = cur.fetchall()
        
        if not rows:
            print("No rows found for today's date")
            return
            
        print(f"\nFound {len(rows)} rows for {current_date}:")
        print("-" * 120)
        print(f"{'corp_id':<40} {'ai_processed':<12} {'sent_to_supabase':<15} {'category':<25} {'has_ai_summary':<15}")
        print("-" * 120)
        
        needs_ai = 0
        needs_upload = 0
        
        for row in rows:
            corp_id = row["corp_id"][:36]  # Truncate for display
            ai_processed = row["ai_processed"] if row["ai_processed"] is not None else 0
            sent_to_supabase = row["sent_to_supabase"] if row["sent_to_supabase"] is not None else 0
            category = (row["category"] or "")[:23]  # Truncate for display
            has_ai_summary = "Yes" if row["ai_summary"] else "No"
            
            print(f"{corp_id:<40} {ai_processed:<12} {sent_to_supabase:<15} {category:<25} {has_ai_summary:<15}")
            
            if not ai_processed:
                needs_ai += 1
            if not sent_to_supabase:
                needs_upload += 1
        
        print("-" * 120)
        print(f"Summary: {needs_ai} need AI processing, {needs_upload} need Supabase upload")
        
        # Check for rows that are AI processed but not uploaded
        if needs_upload > 0:
            print(f"\nRows needing Supabase upload:")
            cur.execute("""
                SELECT corp_id, category, ai_processed, sent_to_supabase 
                FROM corporatefilings 
                WHERE (date LIKE ? OR date = ?) 
                AND (sent_to_supabase IS NULL OR sent_to_supabase = 0)
                ORDER BY corp_id
            """, (f"{current_date}%", current_date))
            
            upload_rows = cur.fetchall()
            for row in upload_rows:
                print(f"  {row['corp_id']} - category: '{row['category']}', ai_processed: {row['ai_processed']}")
        
    except Exception as e:
        print(f"Error checking database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_db_state()