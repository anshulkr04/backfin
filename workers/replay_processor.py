#!/usr/bin/env python3
"""
replay_unsent_to_supabase.py

Replay unsent local `corporatefilings` rows to Supabase for a given date.

Usage:
    python replay_unsent_to_supabase.py --date 2025-09-26

This script expects the local SQLite DB at ./data/bse_raw.db (relative to this file).
It reads environment variables SUPABASE_URL2 and SUPABASE_KEY2 (or SUPABASE_SERVICE_ROLE_KEY).
"""

import os
import argparse
import logging
import sqlite3
import time
import json
import requests
import tempfile
import shutil
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from collections import deque
from urllib.parse import urlparse
load_dotenv()

# Optional imports
try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = None

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

from pydantic import BaseModel, Field

# Import functions from other files
try:
    from src.ai.prompts import all_prompt, category_prompt, headline_prompt, sum_prompt, financial_data_prompt
    from src.services.investor_analyzer import uploadInvestor
except ImportError as e:
    logging.warning(f"Could not import some modules: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("replay_unsent")

# StrucOutput for AI processing
class StrucOutput(BaseModel):
    """Schema for structured output from the model."""
    category: str = Field(..., description=category_prompt)
    headline: str = Field(..., description=headline_prompt)
    summary: str = Field(..., description=sum_prompt)
    findata: str = Field(..., description=financial_data_prompt)
    individual_investor_list: list[str] = Field(..., description="List of individual investors not company mentioned in the announcement. It should be in a form of an array of strings.")
    company_investor_list: list[str] = Field(..., description="List of company investors mentioned in the announcement. It should be in a form of an array of strings.")
    sentiment: str = Field(..., description="Analyze the sentiment of the announcement and give appropriate output. The output should be only: Postive, Negative and Netural. Nothing other than these.")

# Local DB path (same layout as your scraper)
LOCAL_DB_PATH = Path(__file__).parent / "data" / "bse_raw.db"

# Supabase env vars (match names used in your main script)
SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_KEY2")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Gemini API
API_KEY = os.getenv("GEMINI_API_KEY")

class RateLimitedGeminiClient:
    def __init__(self, api_key, rpm_limit=4000, max_retries=3):
        try:
            self.client = genai.Client(api_key=api_key)
            self.rpm_limit = rpm_limit
            self.request_timestamps = deque()
            self.max_retries = max_retries
            logger.info("Gemini client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.client = None

    def _enforce_rate_limit(self):
        """Enforce API rate limit (requests per minute)"""
        if not self.client:
            raise Exception("Gemini client not initialized")
            
        current_time = time.time()
        while self.request_timestamps and current_time - self.request_timestamps[0] > 60:
            self.request_timestamps.popleft()

        if len(self.request_timestamps) >= self.rpm_limit:
            wait_time = 60 - (current_time - self.request_timestamps[0]) + 0.1
            logger.info(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
            time.sleep(wait_time)

        self.request_timestamps.append(time.time())

    def generate_content(self, contents, config):
        """Rate-limited wrapper for generate_content with retries"""
        if not self.client:
            raise Exception("Gemini client not initialized")
        model = "gemini-2.5-flash-lite-preview-06-17"
            
        for attempt in range(1, self.max_retries + 1):
            try:
                self._enforce_rate_limit()
                return self.client.models.generate_content(model=model, contents=contents, config=config)
            except Exception as e:
                if attempt == self.max_retries:
                    logger.error(f"Failed to generate content after {self.max_retries} attempts: {e}")
                    raise
                logger.warning(f"Attempt {attempt} failed: {e}. Retrying...")
                time.sleep(2 * attempt)  # Exponential backoff

    @property
    def files(self):
        """Expose the original client's .files attribute"""
        if not self.client:
            raise Exception("Gemini client not initialized")
        return self.client.files

# Initialize Gemini client
genai_client = None
try:
    if API_KEY and GENAI_AVAILABLE:
        genai_client = RateLimitedGeminiClient(api_key=API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    logger.warning("AI processing will be skipped")

def remove_markdown_tags(text):
    """Remove Markdown tags and adjust indentation of the text"""
    if not isinstance(text, str):
        logger.warning(f"Expected string for markdown removal, got {type(text)}")
        return "" if text is None else str(text)
        
    # Check if code blocks are present
    has_code_blocks = re.search(r'```', text) is not None

    # Remove code blocks (content between ```)
    text = re.sub(r'```[^\n]*\n(.*?)```', r'\1', text, flags=re.DOTALL)
    
    # Remove HTML tags
    text = re.sub(r"<.*?>", "", text)
    
    # Only adjust indentation if code blocks were detected
    if has_code_blocks:
        lines = text.split('\n')
        if lines:
            # Find the minimum indentation (excluding empty lines)
            non_empty_lines = [line for line in lines if line.strip()]
            if non_empty_lines:
                min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines)
                # Reduce indentation by half of the minimum (to maintain some indentation)
                shift = max(min_indent // 2, 1) if min_indent > 0 else 0
                lines = [line[shift:] if line.strip() else line for line in lines]
            text = '\n'.join(lines)
    
    return text.strip()

def clean_summary(text):
    """Removes everything before **Category:** and returns the rest."""
    marker = "**Category:**"
    if marker in text:
        return text[text.index(marker):].strip()
    else:
        return text

def check_for_negative_keywords(summary):
    """Check for negative keywords in the announcements"""
    if not isinstance(summary, str):
        logger.warning(f"Expected string for keyword check, got {type(summary)}")
        return True  # Treat non-string values as containing negative keywords
        
    negative_keywords = [
        "Trading Window", "Compliance Report", "Advertisement(s)", "Advertisement", "Public Announcement",
        "Share Certificate(s)", "Share Certificate", "Depositories and Participants", "Depository and Participant",
        "Depository and Participant", "Depository and Participants", "74(5)", "XBRL", "Newspaper Publication",
        "Published in the Newspapers", "Clippings", "Book Closure", "Change in Company Secretary/Compliance Officer",
        "Record Date","Code of Conduct","Cessation","Deviation","Declared Interim Dividend","IEPF","Investor Education","Registrar & Share Transfer Agent",
        "Registrar and Share Transfer Agent","Scrutinizers report","Utilisation of Funds","Postal Ballot","Defaults on Payment of Interest",
        "Newspaper Publication","Sustainability Report","Sustainability Reporting","Trading Plan","Letter of Confirmation","Forfeiture/Cancellation","Price movement",
        "Spurt","Grievance Redressal","Monitoring Agency","Regulation 57",
    ]

    special_keywords = [
        "Board", "Outcome", "General Updates",
    ]

    for keyword in special_keywords:
        if keyword.lower() in summary.lower():
            logger.info(f"Special keyword '{keyword}' found in announcement: {summary}")
            return False
            
    for keyword in negative_keywords:
        if keyword.lower() in summary.lower():
            logger.info(f"Negative keyword '{keyword}' found in announcement: {summary}")
            return True
            
    return False

def check_for_pdf(desc):
    """Check if the description contains a PDF file name"""
    return isinstance(desc, str) and desc.lower().endswith('.pdf')

def get_pdf_page_count(filepath):
    """Get the number of pages in a PDF file"""
    if not PDF_SUPPORT:
        logger.warning("PyPDF2 not installed, cannot count PDF pages")
        return None
    
    try:
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            page_count = len(pdf_reader.pages)
            logger.info(f"PDF has {page_count} pages")
        return page_count
    except Exception as e:
        logger.error(f"Error counting PDF pages: {e}")
        return None

def download_pdf(pdf_file, temp_dir, max_retries=3, request_timeout=30):
    """Download PDF file with error handling"""
    if not pdf_file:
        logger.error("No PDF file specified")
        return None, "No PDF file specified"
        
    filepath = os.path.join(temp_dir, pdf_file.split("/")[-1])
    
    try:
        url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{pdf_file}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.bseindia.com/",
            "Origin": "https://www.bseindia.com"
        }
        
        # Download with retries
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(url, timeout=request_timeout, headers=headers)
                response.raise_for_status()
                
                with open(filepath, "wb") as file:
                    file.write(response.content)
                logger.info(f"Downloaded: {filepath}")
                return filepath, None
            except requests.exceptions.RequestException as e:
                logger.error(f"Error downloading PDF (attempt {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    return None, f"Failed to download PDF: {str(e)}"
                time.sleep(5)
                
    except Exception as e:
        logger.error(f"Unexpected error downloading PDF: {e}")
        return None, f"Unexpected error: {str(e)}"

def ai_process_pdf(filepath):
    """Process PDF with AI, with proper error handling"""
    if not filepath:
        logger.error("No valid filename provided for AI processing")
        return "Error", "No valid filename provided", "", "", [], [], "Neutral"
        
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return "Error", "File not found", "", "", [], [], "Neutral"
        
    # Handle case where Gemini client failed to initialize
    if not genai_client:
        logger.error("Cannot process file: Gemini client not initialized")
        return "Procedural/Administrative", "AI processing unavailable", "", "", [], [], "Neutral"

    uploaded_file = None
    
    try:
        logger.info(f"Uploading file: {filepath}")
        # Upload the PDF file
        uploaded_file = genai_client.files.upload(file=filepath)
        
        # Generate content with structured output
        response = genai_client.generate_content(
            contents=[all_prompt, uploaded_file],
            config={
                "response_mime_type": "application/json",
                "response_schema": list[StrucOutput]
            },
        )
        
        if not hasattr(response, 'text'):
            logger.error("AI response missing text attribute")
            return "Error", "AI processing failed: invalid response format", "", "", [], [], "Neutral"
            
        # Parse JSON response
        summary = json.loads(response.text.strip())
        
        # Extract all fields from the summary
        try:
            category_text = summary[0]["category"]
            headline = summary[0]["headline"]
            summary_text = summary[0]["summary"]
            financial_data = summary[0]["findata"]
            individual_investor_list = summary[0]["individual_investor_list"]
            company_investor_list = summary[0]["company_investor_list"]
            sentiment = summary[0]["sentiment"]
            
            logger.info(f"AI processing completed successfully for {filepath}")
            logger.info(f"Category: {category_text}")
            return category_text, summary_text, headline, financial_data, individual_investor_list, company_investor_list, sentiment
        except (IndexError, KeyError) as e:
            logger.error(f"Failed to extract fields from AI response: {e}")
            return "Error", "Failed to extract fields from AI response", "", "", [], [], "Neutral"
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from AI response: {e}")
        return "Error", "Failed to parse AI response", "", "", [], [], "Neutral"
    except Exception as e:
        logger.error(f"Error in AI processing: {e}")
        return "Error", f"Error processing file: {str(e)}", "", "", [], [], "Neutral"

def safely_upload_financial_data(supabase, financial_data, symbol, isin, max_retries=3):
    """Safely upload financial data with proper duplicate checking and updating"""
    try:
        # Check if record exists for this ISIN and period
        existing_query = supabase.table("financial_results").select("*").eq("isin", isin)
        
        # Only filter by period if it's not empty
        if financial_data.get("period"):
            existing_query = existing_query.eq("period", financial_data.get("period"))
            
        existing_result = existing_query.execute()
        
        if existing_result.data and len(existing_result.data) > 0:
            existing_record = existing_result.data[0]
            logger.info(f"Found existing financial record for ISIN {isin}, period: {financial_data.get('period')}")
            
            # Check if existing record has missing data that we can fill
            update_needed = False
            update_data = {}
            
            for field in ["sales_current", "sales_previous_year", "pat_current", "pat_previous_year"]:
                existing_value = existing_record.get(field)
                new_value = financial_data.get(field)
                
                # Update if existing field is empty/null and new value is not empty
                if (not existing_value or existing_value.strip() == "") and new_value and new_value.strip():
                    update_data[field] = new_value
                    update_needed = True
            
            if update_needed:
                # Update the existing record
                for attempt in range(1, max_retries + 1):
                    try:
                        update_result = supabase.table("financial_results").update(update_data).eq("isin", isin).eq("period", financial_data.get("period", "")).execute()
                        logger.info(f"Updated financial data for {symbol} (ISIN: {isin}) with missing fields")
                        return True
                    except Exception as e:
                        logger.error(f"Error updating financial data (attempt {attempt}/{max_retries}): {e}")
                        if attempt < max_retries:
                            time.sleep(5)
                        else:
                            logger.error(f"Failed to update financial data after {max_retries} attempts")
                            return False
            else:
                logger.info(f"Financial data for {symbol} (ISIN: {isin}) already complete, skipping")
                return True
        else:
            # No existing record, insert new one
            # First verify corp_id exists in corporatefilings to avoid FK constraint violation
            corp_id = financial_data.get("corp_id")
            if corp_id:
                try:
                    corp_check = supabase.table("corporatefilings").select("corp_id").eq("corp_id", corp_id).limit(1).execute()
                    if not corp_check.data or len(corp_check.data) == 0:
                        logger.error(f"corp_id {corp_id} not found in corporatefilings - skipping financial data insert")
                        return False
                except Exception as check_err:
                    logger.error(f"Error verifying corp_id existence: {check_err}")
                    return False
            
            for attempt in range(1, max_retries + 1):
                try:
                    insert_result = supabase.table("financial_results").insert(financial_data).execute()
                    logger.info(f"Inserted new financial data for {symbol} (ISIN: {isin})")
                    return True
                except Exception as e:
                    err_text = str(e)
                    logger.error(f"Error inserting financial data (attempt {attempt}/{max_retries}): {err_text}")
                    
                    # If FK constraint violation, don't retry
                    if "23503" in err_text or "violates foreign key constraint" in err_text:
                        logger.error(f"Foreign key constraint violation - corp_id {corp_id} not in corporatefilings")
                        return False
                    
                    if attempt < max_retries:
                        time.sleep(5)
                    else:
                        logger.error(f"Failed to insert financial data after {max_retries} attempts")
                        return False
    except Exception as e:
        logger.error(f"Error in safely_upload_financial_data: {e}")
        return False

def safe_row_get(row, key, default=None):
    """Safely get value from SQLite row object or dict"""
    try:
        if hasattr(row, 'keys') and key in row.keys():
            value = row[key]
            return value if value is not None else default
        else:
            return default
    except (KeyError, TypeError):
        return default

def get_supabase_client():
    """Return a supabase client if env vars present, else None."""
    if create_client is None:
        logger.error("supabase package not available. Please `pip install supabase` to enable Supabase uploads.")
        return None

    if not SUPABASE_URL or not (SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY):
        logger.error("Supabase credentials not found in environment (SUPABASE_URL2 / SUPABASE_KEY2).")
        return None

    key = SUPABASE_SERVICE_ROLE_KEY if SUPABASE_SERVICE_ROLE_KEY else SUPABASE_KEY
    try:
        client = create_client(SUPABASE_URL, key)
        logger.info("Supabase client initialized")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None

def mark_local_sent_to_supabase(conn, corp_id, db_path=None):
    """Mark local corporatefilings row as sent_to_supabase = 1 and set timestamp."""
    try:
        now_ts = datetime.now(timezone.utc).isoformat()
        cur = conn.cursor()
        cur.execute(
            "UPDATE corporatefilings SET sent_to_supabase = 1, sent_to_supabase_at = ? WHERE corp_id = ?",
            (now_ts, corp_id)
        )
        conn.commit()
        logger.debug(f"Marked local corp_id {corp_id} as sent")
        return True
    except Exception as e:
        logger.error(f"Failed to mark local corp_id {corp_id} as sent: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False

def mark_local_ai_processed(conn, corp_id, ai_summary=None, ai_error=None, category=None, headline=None, sentiment=None):
    """Mark local corporatefilings row as AI processed with results"""
    try:
        now_ts = datetime.now(timezone.utc).isoformat()
        cur = conn.cursor()
        
        update_fields = ["ai_processed = ?", "ai_processed_at = ?"]
        update_values = [1 if ai_error is None else 0, now_ts]
        
        if ai_summary is not None:
            update_fields.append("ai_summary = ?")
            update_values.append(ai_summary)
        
        if ai_error is not None:
            update_fields.append("ai_error = ?")
            update_values.append(ai_error)
            
        if category is not None:
            update_fields.append("category = ?")
            update_values.append(category)
            
        if headline is not None:
            update_fields.append("headline = ?")
            update_values.append(headline)
            
        if sentiment is not None:
            update_fields.append("sentiment = ?")
            update_values.append(sentiment)
        
        update_values.append(corp_id)
        
        query = f"UPDATE corporatefilings SET {', '.join(update_fields)} WHERE corp_id = ?"
        cur.execute(query, update_values)
        conn.commit()
        logger.debug(f"Marked local corp_id {corp_id} as AI processed")
        return True
    except Exception as e:
        logger.error(f"Failed to mark local corp_id {corp_id} as AI processed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False

def fetch_rows_needing_processing(conn, date_str, batch=500):
    """
    Fetch rows for the provided date where:
    1. sent_to_supabase is NULL or 0, OR
    2. ai_processed is NULL or 0 (needs AI processing)
    Date matching is permissive: it checks equality and also prefixes (handles iso and compact formats).
    """
    cur = conn.cursor()
    # Prepare possible date patterns:
    # Accept date like 2025-09-26 or 20250926
    compact = date_str.replace("-", "")
    like_iso = f"{date_str}%"
    like_compact = f"{compact}%"

    query = """
        SELECT * FROM corporatefilings
        WHERE (
            (sent_to_supabase IS NULL OR sent_to_supabase = 0) OR
            (ai_processed IS NULL OR ai_processed = 0)
        )
        AND (
            date = ?
            OR date LIKE ?
            OR date LIKE ?
        )
        LIMIT ?
    """
    cur.execute(query, (date_str, like_iso, like_compact, batch))
    rows = cur.fetchall()
    
    # Debug logging
    if rows:
        logger.info(f"Found {len(rows)} rows needing processing:")
        for row in rows[:5]:  # Log first 5 rows for debugging
            corp_id = row["corp_id"]
            ai_processed = row["ai_processed"] if row["ai_processed"] is not None else 0
            sent_to_supabase = row["sent_to_supabase"] if row["sent_to_supabase"] is not None else 0
            category = row["category"] if row["category"] is not None else ""
            logger.info(f"  corp_id={corp_id}, ai_processed={ai_processed}, sent_to_supabase={sent_to_supabase}, category='{category}'")
    
    return rows

def row_to_payload(row):
    """Convert sqlite row tuple / dict to dict payload for Supabase insert."""
    # Handle sqlite3.Row objects which are dict-like but not exactly dicts
    def safe_get(key, default=None):
        try:
            value = row[key]
            return value if value is not None else default
        except (KeyError, TypeError, IndexError):
            return default
    
    payload = {
        "corp_id": safe_get("corp_id"),
        "securityid": safe_get("securityid"),
        "summary": safe_get("summary"),
        "fileurl": safe_get("fileurl"),
        "date": safe_get("date"),
        "ai_summary": safe_get("ai_summary"),
        "category": safe_get("category"),
        "isin": safe_get("isin"),
        "companyname": safe_get("companyname"),
        "symbol": safe_get("symbol"),
        "headline": safe_get("headline"),
        "sentiment": safe_get("sentiment"),
        "company_id": safe_get("company_id"),
    }
    return payload

def replay_unsent_to_supabase(date_str, batch=100, retry_per_row=3, wait_between_retries=2, enable_ai_processing=True):
    """Main replay function. Returns (attempted, succeeded, ai_processed)."""
    supabase_client = get_supabase_client()
    if not supabase_client:
        logger.error("Supabase client not available. Aborting replay.")
        return 0, 0, 0

    if not LOCAL_DB_PATH.exists():
        logger.error(f"Local DB not found at {LOCAL_DB_PATH}")
        return 0, 0, 0

    conn = sqlite3.connect(str(LOCAL_DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    attempted = 0
    succeeded = 0
    ai_processed = 0
    
    # Create temporary directory for PDF downloads
    temp_dir = tempfile.mkdtemp(prefix="replay_scraper_")
    logger.info(f"Created temporary directory: {temp_dir}")

    try:
        # Get all rows that need processing (AI or Supabase upload)
        rows = fetch_rows_needing_processing(conn, date_str, batch=batch)
        
        if not rows:
            logger.info(f"No rows found needing processing for date {date_str}")
            return 0, 0, 0
            
        logger.info(f"Found {len(rows)} rows needing processing")
        
        for r in rows:
            attempted += 1
            corp_id = r["corp_id"]
            ai_processed_flag = r["ai_processed"] if r["ai_processed"] is not None else 0
            sent_to_supabase_flag = r["sent_to_supabase"] if r["sent_to_supabase"] is not None else 0
            ai_processed_in_this_run = False
            
            logger.info(f"Processing corp_id={corp_id}, ai_processed={ai_processed_flag}, sent_to_supabase={sent_to_supabase_flag}")
            
            # First, handle AI processing if needed
            if enable_ai_processing and not ai_processed_flag:
                logger.info(f"Starting AI processing for corp_id={corp_id}")
                if process_ai_for_row(r, conn, temp_dir, supabase_client):
                    ai_processed += 1
                    ai_processed_in_this_run = True
                    # Refresh the row data after AI processing
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM corporatefilings WHERE corp_id = ?", (corp_id,))
                    r = cur.fetchone()
                    if not r:
                        logger.error(f"Row disappeared after AI processing: corp_id={corp_id}")
                        continue
            
            # Then, handle Supabase upload/update if needed
            sent_to_supabase_flag = r["sent_to_supabase"] if r["sent_to_supabase"] is not None else 0
            category = r["category"] if r["category"] is not None else ""
            
            # Check if we just processed this row with AI and it was already sent to Supabase
            if sent_to_supabase_flag and ai_processed_in_this_run:
                # This row was AI processed in this run and already exists in Supabase - update it
                logger.info(f"Updating existing Supabase row: corp_id={corp_id}, category='{category}'")
                
                success = False
                last_err = None
                
                for attempt in range(1, retry_per_row + 1):
                    try:
                        # Update the existing row in Supabase with new AI data
                        update_payload = {
                            "category": r["category"],
                            "ai_summary": r["ai_summary"],
                            "headline": r["headline"],
                            "sentiment": r["sentiment"]
                        }
                        
                        response = supabase_client.table("corporatefilings").update(update_payload).eq("corp_id", corp_id).execute()
                        logger.info(f"Successfully updated Supabase row: corp_id={corp_id} with category='{category}'")
                        succeeded += 1
                        success = True
                        break
                    except Exception as e:
                        last_err = e
                        logger.warning("Attempt %d/%d failed to update corp_id %s: %s", attempt, retry_per_row, corp_id, e)
                        if attempt < retry_per_row:
                            time.sleep(wait_between_retries * attempt)
                
                if not success:
                    logger.error("Failed to update corp_id=%s after %d attempts. Last error: %s", corp_id, retry_per_row, last_err)
                    
            elif not sent_to_supabase_flag:
                # Row not yet sent to Supabase - insert it
                logger.info(f"Uploading to Supabase: corp_id={corp_id}, category='{category}'")
                
                # Skip if category is Procedural/Administrative
                if category == "Procedural/Administrative":
                    logger.info(f"Skipping Supabase upload for corp_id={corp_id} (Procedural/Administrative)")
                    # Still mark as sent to avoid reprocessing
                    mark_local_sent_to_supabase(conn, corp_id)
                    succeeded += 1
                    continue
                
                payload = row_to_payload(r)
                success = False
                last_err = None

                for attempt in range(1, retry_per_row + 1):
                    try:
                        # Insert into Supabase
                        response = supabase_client.table("corporatefilings").insert(payload).execute()
                        logger.info(f"Successfully inserted to Supabase: corp_id={corp_id}")
                        
                        # Mark local as sent
                        mark_local_sent_to_supabase(conn, corp_id)
                        
                        # Handle financial data and investor data upload
                        upload_additional_data(r, supabase_client)
                        
                        succeeded += 1
                        success = True
                        logger.info("Successfully replayed corp_id=%s", corp_id)
                        break
                    except Exception as e:
                        err_text = str(e)
                        last_err = e
                        logger.warning("Attempt %d/%d failed for corp_id %s: %s", attempt, retry_per_row, corp_id, e)
                        
                        # If duplicate primary-key, stop retrying — row already exists
                        if "duplicate key" in err_text or "23505" in err_text:
                            logger.warning(f"Duplicate key for corp_id {corp_id} — assuming row already exists, stopping insert retries.")
                            mark_local_sent_to_supabase(conn, corp_id)
                            succeeded += 1
                            success = True
                            break
                            
                        if attempt < retry_per_row:
                            time.sleep(wait_between_retries * attempt)

                if not success:
                    logger.error("Failed to replay corp_id=%s after %d attempts. Last error: %s", corp_id, retry_per_row, last_err)
            else:
                logger.info(f"Row corp_id={corp_id} already sent to Supabase and no AI processing needed, skipping")

        return attempted, succeeded, ai_processed

    finally:
        try:
            conn.close()
        except Exception:
            pass
        
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Removed temporary directory: {temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {e}")

def process_ai_for_row(row, conn, temp_dir, supabase_client):
    """Process AI for a single row that needs AI processing"""
    corp_id = row["corp_id"]
    summary = row["summary"] if row["summary"] is not None else ""
    fileurl = row["fileurl"] if row["fileurl"] is not None else ""
    
    logger.info(f"Starting AI processing for corp_id={corp_id}")
    
    # Initialize default values
    ai_summary = None
    category = "Procedural/Administrative"
    headline = ""
    findata = '{"period": "", "sales_current": "", "sales_previous_year": "", "pat_current": "", "pat_previous_year": ""}'
    individual_investor_list = []
    company_investor_list = []
    sentiment = "Neutral"
    ai_error = None
    
    try:
        # Check for negative keywords first
        if check_for_negative_keywords(summary):
            logger.info(f"Negative keyword found in announcement: {summary}")
            ai_summary = "Please refer to the original document provided."
            category = "Procedural/Administrative"
        else:
            # Check if there's a PDF to process
            if fileurl and check_for_pdf(fileurl):
                # Extract filename from URL
                pdf_filename = fileurl.split("/")[-1]
                logger.info(f"Processing PDF: {pdf_filename}")
                
                # Download PDF
                filepath, download_error = download_pdf(pdf_filename, temp_dir)
                
                if filepath and not download_error:
                    # Process with AI
                    category, ai_summary, headline, findata, individual_investor_list, company_investor_list, sentiment = ai_process_pdf(filepath)
                    
                    if ai_summary:
                        ai_summary = remove_markdown_tags(ai_summary)
                        ai_summary = clean_summary(ai_summary)
                    
                    # Clean up PDF file
                    try:
                        os.remove(filepath)
                        logger.info(f"Deleted temporary file: {filepath}")
                    except Exception as e:
                        logger.warning(f"Failed to delete temporary file {filepath}: {e}")
                else:
                    ai_error = download_error or "Failed to download PDF"
                    logger.error(f"PDF download failed: {ai_error}")
            else:
                # No PDF or PDF not processable
                ai_summary = "Please refer to the original document provided."
                category = "Procedural/Administrative"
        
        # Update local database with AI processing results
        mark_local_ai_processed(
            conn, corp_id, 
            ai_summary=ai_summary, 
            ai_error=ai_error,
            category=category,
            headline=headline,
            sentiment=sentiment
        )
        
        logger.info(f"AI processing completed for corp_id={corp_id}, category={category}")
        return True
        
    except Exception as e:
        ai_error = f"AI processing error: {str(e)}"
        logger.error(f"Error in AI processing for corp_id={corp_id}: {e}")
        
        # Mark as processed with error
        mark_local_ai_processed(conn, corp_id, ai_error=ai_error)
        return False

def upload_additional_data(row, supabase_client):
    """Upload financial data and investor data if available"""
    corp_id = row["corp_id"]
    
    try:
        # Handle financial data if available
        category = row["category"] if row["category"] is not None else ""
        if category != "Procedural/Administrative":
            # Parse financial data (assuming it was processed by AI)
            # This would be in the fileurl content or processed separately
            # For now, we'll skip this as it requires the full findata processing logic
            pass
            
        # Handle investor data if available  
        # This would require the individual_investor_list and company_investor_list
        # For now, we'll skip this as it requires the full investor processing logic
        pass
        
    except Exception as e:
        logger.error(f"Error uploading additional data for corp_id={corp_id}: {e}")

def get_current_date():
    """Get current date to check for unprocessed data"""
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d')

def run_continuous_replay(batch=200, retries=3, enable_ai=True, check_interval=60):
    """Run replay continuously, checking for unprocessed data every check_interval seconds"""
    logger.info("Starting continuous replay service...")
    logger.info(f"Check interval: {check_interval} seconds")
    logger.info("Checking current date for unprocessed data")
    logger.info(f"AI processing: {'enabled' if enable_ai else 'disabled'}")
    
    if enable_ai and not genai_client:
        logger.warning("AI processing unavailable (Gemini client not initialized)")
        enable_ai = False
    
    consecutive_empty_runs = 0
    max_empty_runs = 10  # After 10 consecutive empty runs, increase check interval
    
    while True:
        try:
            current_date = get_current_date()
            logger.debug(f"Checking current date: {current_date}")
            
            attempted, succeeded, ai_processed = replay_unsent_to_supabase(
                current_date, 
                batch=batch, 
                retry_per_row=retries, 
                enable_ai_processing=enable_ai
            )
            
            if attempted == 0:
                consecutive_empty_runs += 1
                logger.debug(f"No unprocessed data found for {current_date} (consecutive empty runs: {consecutive_empty_runs})")
            else:
                consecutive_empty_runs = 0
                logger.info(f"Date {current_date}: Attempted: {attempted}, Succeeded: {succeeded}, AI Processed: {ai_processed}")
            
            # Adaptive sleep - increase interval if no work found for a while
            current_interval = check_interval
            if consecutive_empty_runs > max_empty_runs:
                current_interval = min(check_interval * 2, 300)  # Max 5 minutes
                logger.debug(f"No work found for {consecutive_empty_runs} cycles, using longer interval: {current_interval}s")
            
            logger.debug(f"Sleeping for {current_interval} seconds...")
            time.sleep(current_interval)
            
        except KeyboardInterrupt:
            logger.info("Continuous replay service stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in continuous replay: {e}")
            logger.info(f"Continuing after error, sleeping for {check_interval} seconds...")
            time.sleep(check_interval)

def main():
    parser = argparse.ArgumentParser(description="Replay unsent local corporatefilings rows to Supabase")
    parser.add_argument("--date", help="Date to replay for (example: 2025-09-26). If not provided, runs in continuous mode")
    parser.add_argument("--batch", type=int, default=200, help="Number of rows to fetch in one run (default 200)")
    parser.add_argument("--retries", type=int, default=3, help="Number of retries per row when inserting to Supabase")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI processing (only handle Supabase uploads)")
    parser.add_argument("--continuous", action="store_true", help="Run in continuous mode (check every minute)")
    parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds for continuous mode (default 60)")
    args = parser.parse_args()

    enable_ai = not args.no_ai
    
    if not enable_ai:
        logger.info("AI processing disabled")
    elif not genai_client:
        logger.warning("AI processing unavailable (Gemini client not initialized)")
        enable_ai = False
    
    # If no date provided or continuous flag set, run in continuous mode
    if not args.date or args.continuous:
        logger.info("Running in continuous mode...")
        run_continuous_replay(
            batch=args.batch,
            retries=args.retries,
            enable_ai=enable_ai,
            check_interval=args.interval
        )
    else:
        # Single run mode
        date_str = args.date.strip()
        logger.info("Starting single replay for date: %s (AI processing: %s)", date_str, "enabled" if enable_ai else "disabled")
        attempted, succeeded, ai_processed = replay_unsent_to_supabase(
            date_str, 
            batch=args.batch, 
            retry_per_row=args.retries, 
            enable_ai_processing=enable_ai
        )
        logger.info("Replay complete. Attempted: %d, Succeeded: %d, AI Processed: %d", attempted, succeeded, ai_processed)

if __name__ == "__main__":
    main()
