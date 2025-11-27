#!/usr/bin/env python3
"""
Unified Corporate Actions Collector for NSE and BSE data.
Collects, normalizes, deduplicates, and uploads to Supabase.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
load_dotenv()

# Import existing scrapers
from corpactbse import fetch_bse
from corpactnse import fetch_nse_corporate_actions

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('CorporateActionsCollector')

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL2')
SUPABASE_KEY = os.getenv('SUPABASE_KEY2')
TABLE_NAME = 'corporate_actions'

# Action required keywords
ACTION_KEYWORDS = [
    'bonus issue',
    'bonus',
    'stock split',
    'split',
    'sub-division',
    'subdivision',
    'reverse split',
    'consolidation',
    'rights issue',
    'spin-off',
    'spinoff',
    'reduction of capital'
]


class CorporateActionsCollector:
    """Collects and processes corporate actions data from NSE and BSE"""
    
    def __init__(self):
        """Initialize the collector with Supabase client"""
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
        
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Initialized CorporateActionsCollector")
    
    def parse_date(self, date_str: str, format_type: str = 'bse') -> Optional[str]:
        """
        Parse date string to YYYY-MM-DD format.
        
        Args:
            date_str: Date string to parse
            format_type: 'bse' for "25 Nov 2025" or 'nse' for "25-Nov-2025"
        
        Returns:
            Date string in YYYY-MM-DD format or None
        """
        if not date_str or date_str == '-' or date_str == '':
            return None
        
        try:
            if format_type == 'bse':
                # Format: "25 Nov 2025"
                dt = datetime.strptime(date_str, "%d %b %Y")
            else:  # nse
                # Format: "25-Nov-2025"
                dt = datetime.strptime(date_str, "%d-%b-%Y")
            
            return dt.strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_str}' with format {format_type}: {e}")
            return None
    
    def check_action_required(self, purpose: str) -> bool:
        """
        Check if the purpose/subject requires action (price adjustment).
        
        Args:
            purpose: Purpose/subject string to check
        
        Returns:
            True if action required, False otherwise
        """
        if not purpose:
            return False
        
        purpose_lower = purpose.lower()
        return any(keyword in purpose_lower for keyword in ACTION_KEYWORDS)
    
    def process_bse_data(self, from_date: str, to_date: str) -> pd.DataFrame:
        """
        Fetch and normalize BSE corporate actions data.
        
        Args:
            from_date: Start date in YYYYMMDD format (e.g., "20251125")
            to_date: End date in YYYYMMDD format
        
        Returns:
            DataFrame with normalized BSE data
        """
        logger.info("================================================================================")
        logger.info("STEP 1: Collecting BSE Data")
        logger.info("================================================================================")
        
        try:
            records, _ = fetch_bse(Fdate=from_date, TDate=to_date)
            
            if not records:
                logger.info("BSE: No records found")
                return pd.DataFrame()
            
            logger.info(f"BSE: Retrieved {len(records)} raw records")
            
            # Convert to DataFrame
            df = pd.DataFrame(records)
            
            # Normalize column names and map to unified schema
            normalized = pd.DataFrame({
                'sec_code': df.get('scrip_code'),
                'symbol': df.get('short_name'),
                'company_name': df.get('long_name'),
                'ex_date': df.get('Ex_date', '').apply(lambda x: self.parse_date(x, 'bse')),
                'purpose': df.get('Purpose'),
                'record_date': df.get('RD_Date', '').apply(lambda x: self.parse_date(x, 'bse')),
                'bc_start_date': df.get('BCRD_FROM', '').apply(lambda x: self.parse_date(x, 'bse')),
                'bc_end_date': df.get('BCRD_TO', '').apply(lambda x: self.parse_date(x, 'bse')),
                'nd_start_date': df.get('ND_START_DATE', '').apply(lambda x: self.parse_date(x, 'bse')),
                'nd_end_date': df.get('ND_END_DATE', '').apply(lambda x: self.parse_date(x, 'bse')),
                'payment_date': df.get('payment_date', '').apply(lambda x: self.parse_date(x, 'bse')),
                'exchange': 'BSE',
                'isin': None,
                'series': None,
                'face_value': None
            })
            
            # Add action_required column
            normalized['action_required'] = normalized['purpose'].apply(self.check_action_required)
            
            # Log data quality
            logger.info(f"BSE: Data quality check:")
            for col in ['sec_code', 'symbol', 'ex_date', 'purpose', 'company_name']:
                non_null = normalized[col].notna().sum()
                pct = (non_null / len(normalized) * 100) if len(normalized) > 0 else 0
                logger.info(f"  {col}: {non_null}/{len(normalized)} non-null values ({pct:.1f}%)")
            
            action_req_count = normalized['action_required'].sum()
            logger.info(f"  action_required: {action_req_count} records require action")
            
            logger.info(f"BSE: Processed {len(normalized)} records")
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error processing BSE data: {e}", exc_info=True)
            return pd.DataFrame()
    
    def process_nse_data(self, from_date: str, to_date: str) -> pd.DataFrame:
        """
        Fetch and normalize NSE corporate actions data.
        
        Args:
            from_date: Start date in DD-MM-YYYY format (e.g., "24-11-2025")
            to_date: End date in DD-MM-YYYY format
        
        Returns:
            DataFrame with normalized NSE data
        """
        logger.info("================================================================================")
        logger.info("STEP 2: Collecting NSE Data")
        logger.info("================================================================================")
        
        try:
            records, _ = fetch_nse_corporate_actions(from_date, to_date)
            
            if not records:
                logger.info("NSE: No records found")
                return pd.DataFrame()
            
            logger.info(f"NSE: Retrieved {len(records)} raw records")
            
            # Convert to DataFrame
            df = pd.DataFrame(records)
            
            # Normalize column names and map to unified schema
            normalized = pd.DataFrame({
                'sec_code': None,  # Will be populated by database trigger
                'symbol': df.get('symbol'),
                'company_name': df.get('comp'),
                'ex_date': df.get('exDate', '').apply(lambda x: self.parse_date(x, 'nse')),
                'purpose': df.get('subject'),
                'record_date': df.get('recDate', '').apply(lambda x: self.parse_date(x, 'nse')),
                'bc_start_date': df.get('bcStartDate', '').apply(lambda x: self.parse_date(x, 'nse')),
                'bc_end_date': df.get('bcEndDate', '').apply(lambda x: self.parse_date(x, 'nse')),
                'nd_start_date': df.get('ndStartDate', '').apply(lambda x: self.parse_date(x, 'nse')),
                'nd_end_date': df.get('ndEndDate', '').apply(lambda x: self.parse_date(x, 'nse')),
                'payment_date': None,  # NSE doesn't provide payment date
                'exchange': 'NSE',
                'isin': df.get('isin'),
                'series': df.get('series'),
                'face_value': df.get('faceVal')
            })
            
            # Add action_required column
            normalized['action_required'] = normalized['purpose'].apply(self.check_action_required)
            
            # Log data quality
            logger.info(f"NSE: Data quality check:")
            for col in ['symbol', 'ex_date', 'purpose', 'company_name', 'isin']:
                non_null = normalized[col].notna().sum()
                pct = (non_null / len(normalized) * 100) if len(normalized) > 0 else 0
                logger.info(f"  {col}: {non_null}/{len(normalized)} non-null values ({pct:.1f}%)")
            
            action_req_count = normalized['action_required'].sum()
            logger.info(f"  action_required: {action_req_count} records require action")
            
            logger.info(f"NSE: Processed {len(normalized)} records")
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error processing NSE data: {e}", exc_info=True)
            return pd.DataFrame()
    
    def get_existing_records_from_db(self, date_from: str, date_to: str) -> Set[str]:
        """
        Query database for existing corporate actions records.
        
        Args:
            date_from: Start date in YYYY-MM-DD format
            date_to: End date in YYYY-MM-DD format
        
        Returns:
            Set of deduplication keys
        """
        try:
            logger.info(f"Fetching existing records from database for date range: {date_from} to {date_to}")
            
            # Query database for records in the date range
            response = self.supabase.table(TABLE_NAME)\
                .select('symbol,ex_date,purpose')\
                .gte('ex_date', date_from)\
                .lte('ex_date', date_to)\
                .execute()
            
            existing_records = response.data if response.data else []
            logger.info(f"Found {len(existing_records)} existing records in database")
            
            # Create deduplication keys from existing records
            existing_keys = set()
            for record in existing_records:
                key = (
                    str(record.get('symbol', '')).strip().lower() + '|' +
                    str(record.get('ex_date', '')) + '|' +
                    str(record.get('purpose', '')).strip().lower()
                )
                existing_keys.add(key)
            
            logger.info(f"Created {len(existing_keys)} unique keys from existing records")
            if existing_keys:
                logger.info(f"Sample existing key: {list(existing_keys)[0]}")
            
            return existing_keys
            
        except Exception as e:
            logger.error(f"Error fetching existing records: {e}")
            # Return empty set to continue processing (will attempt to insert, may fail on duplicates)
            return set()
    
    def deduplicate_data(self, df: pd.DataFrame, existing_keys: Set[str] = None) -> pd.DataFrame:
        """
        Deduplicate corporate actions records.
        Priority: NSE over BSE (NSE has ISIN and more standardized data).
        
        Args:
            df: Combined DataFrame with NSE and BSE data
            existing_keys: Set of deduplication keys from database
        
        Returns:
            Deduplicated DataFrame
        """
        if df.empty:
            return df
        
        logger.info(f"Deduplication: Starting with {len(df)} total records")
        
        # Filter out invalid records (missing critical fields)
        initial_count = len(df)
        df = df[
            (df['symbol'].notna()) & 
            (df['symbol'] != '') &
            (df['ex_date'].notna()) &
            (df['purpose'].notna()) &
            (df['purpose'] != '')
        ].copy()
        invalid_count = initial_count - len(df)
        if invalid_count > 0:
            logger.info(f"Deduplication: Filtered out {invalid_count} invalid records (missing symbol, ex_date, or purpose)")
        
        if df.empty:
            logger.info("Deduplication: No valid records remaining after filtering invalid data")
            return df
        
        # Create deduplication key: symbol + ex_date + purpose
        df['dedup_key'] = (
            df['symbol'].fillna('').str.strip().str.lower() + '|' +
            df['ex_date'].fillna('').astype(str) + '|' +
            df['purpose'].fillna('').str.strip().str.lower()
        )
        
        if len(df) > 0:
            logger.info(f"Sample new key: {df['dedup_key'].iloc[0]}")
        
        # First, filter out records that already exist in database
        if existing_keys:
            initial_count = len(df)
            df = df[~df['dedup_key'].isin(existing_keys)]
            filtered_count = initial_count - len(df)
            if filtered_count > 0:
                logger.info(f"Deduplication: Filtered out {filtered_count} records that already exist in database")
        
        if df.empty:
            logger.info("Deduplication: No new records to upload after filtering existing records")
            return df
        
        # Count duplicates within new data
        duplicates = df[df.duplicated(subset=['dedup_key'], keep=False)]
        if not duplicates.empty:
            logger.info(f"Deduplication: Found {len(duplicates)} duplicate records in new data")
        
        # Sort by exchange (NSE first) to prefer NSE data
        df['exchange_priority'] = df['exchange'].map({'NSE': 0, 'BSE': 1})
        df_sorted = df.sort_values('exchange_priority')
        
        # Keep first occurrence (which will be NSE if duplicate exists)
        df_deduped = df_sorted.drop_duplicates(subset=['dedup_key'], keep='first')
        
        # Drop helper columns
        df_deduped = df_deduped.drop(columns=['dedup_key', 'exchange_priority'])
        
        removed_count = len(df) - len(df_deduped)
        logger.info(f"Deduplication: Removed {removed_count} duplicates within new data, kept {len(df_deduped)} unique records")
        
        # Log distribution
        exchange_counts = df_deduped['exchange'].value_counts().to_dict()
        logger.info(f"Deduplication: Final distribution - {exchange_counts}")
        
        return df_deduped
    
    def prepare_for_upload(self, df: pd.DataFrame) -> List[Dict]:
        """
        Prepare DataFrame for Supabase upload.
        
        Args:
            df: DataFrame to prepare
        
        Returns:
            List of dictionaries ready for upload
        """
        if df.empty:
            return []
        
        # Convert DataFrame to list of dicts
        records = df.to_dict('records')
        
        # Clean up None/NaN values and ensure proper types
        cleaned_records = []
        for record in records:
            cleaned = {}
            for key, value in record.items():
                # Convert NaN to None
                if pd.isna(value):
                    cleaned[key] = None
                elif isinstance(value, (int, float)) and pd.notna(value):
                    # Keep numeric values as is
                    cleaned[key] = value
                elif value == '' or value == '-':
                    cleaned[key] = None
                else:
                    cleaned[key] = value
            cleaned_records.append(cleaned)
        
        return cleaned_records
    
    def upload_to_supabase(self, records: List[Dict]) -> bool:
        """
        Upload records to Supabase in batches.
        
        Args:
            records: List of records to upload
        
        Returns:
            True if successful, False otherwise
        """
        if not records:
            logger.info("No records to upload")
            return True
        
        logger.info(f"Uploading {len(records)} records in batches of 100")
        
        # Log sample record
        logger.info(f"Sample record before upload: {records[0]}")
        
        batch_size = 100
        success = True
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            try:
                response = self.supabase.table(TABLE_NAME).insert(batch).execute()
                logger.info(f"Uploaded batch {i//batch_size + 1}: {len(batch)} records")
            except Exception as e:
                logger.error(f"Failed to upload batch {i//batch_size + 1}: {e}")
                logger.error(f"Sample record: {batch[0]}")
                success = False
        
        if success:
            logger.info(f"Successfully uploaded {len(records)} records")
            logger.info("✅ Upload completed successfully!")
        else:
            logger.error("❌ Upload failed")
        
        return success
    
    def run(self, days_forward: int = 7):
        """
        Main execution method to collect, process, and upload corporate actions data.
        Collects data for next N days forward from today (for daily cronjob use).
        
        Args:
            days_forward: Number of days to look forward from today (default: 7)
        """
        logger.info("================================================================================")
        logger.info("CORPORATE ACTIONS DATA COLLECTION STARTED")
        logger.info("================================================================================")
        
        # Calculate date range - today to N days forward
        today = datetime.now()
        start_date = today
        end_date = today + timedelta(days=days_forward)
        
        # Format dates for BSE (YYYYMMDD)
        bse_from = start_date.strftime("%Y%m%d")
        bse_to = end_date.strftime("%Y%m%d")
        
        # Format dates for NSE (DD-MM-YYYY)
        nse_from = start_date.strftime("%d-%m-%Y")
        nse_to = end_date.strftime("%d-%m-%Y")
        
        # Format dates for DB query (YYYY-MM-DD)
        db_from = start_date.strftime("%Y-%m-%d")
        db_to = end_date.strftime("%Y-%m-%d")
        
        logger.info(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        logger.info(f"Collecting data for next {days_forward} days forward")
        
        # Collect NSE data
        nse_df = self.process_nse_data(nse_from, nse_to)
        
        # Collect BSE data
        bse_df = self.process_bse_data(bse_from, bse_to)
        
        # FIRST: Fetch existing records from database BEFORE collecting new data
        logger.info("================================================================================")
        logger.info("STEP 3: Fetching Existing Records from Database")
        logger.info("================================================================================")
        
        existing_keys = self.get_existing_records_from_db(db_from, db_to)
        
        # Combine data
        logger.info("================================================================================")
        logger.info("STEP 4: Combining Data")
        logger.info("================================================================================")
        
        if nse_df.empty and bse_df.empty:
            logger.info("No data collected from either exchange")
            return
        
        combined_df = pd.concat([nse_df, bse_df], ignore_index=True)
        logger.info(f"Combined total: {len(combined_df)} records")
        
        # Deduplicate against existing database records
        logger.info("================================================================================")
        logger.info("STEP 5: Deduplication Against Existing Data")
        logger.info("================================================================================")
        
        deduped_df = self.deduplicate_data(combined_df, existing_keys)
        
        if deduped_df.empty:
            logger.info("No new records to upload after deduplication")
            return
        
        # Prepare for upload
        logger.info("================================================================================")
        logger.info("STEP 6: Uploading to Database")
        logger.info("================================================================================")
        
        records = self.prepare_for_upload(deduped_df)
        
        # Upload to Supabase
        self.upload_to_supabase(records)
        
        logger.info("================================================================================")
        logger.info("CORPORATE ACTIONS DATA COLLECTION COMPLETED")
        logger.info("================================================================================")


if __name__ == "__main__":
    try:
        collector = CorporateActionsCollector()
        # Collect data for next 7 days forward (for daily cronjob)
        # This prevents duplicate uploads since we compare against existing DB records
        collector.run(days_forward=7)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
