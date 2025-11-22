#!/usr/bin/env python3
"""
Deduplicator - Removes duplicate deals between NSE and BSE data.

Deduplication logic:
If security code/name/symbol AND client name AND deal type AND quantity AND price match,
then keep BSE record (remove NSE duplicate).
"""

import logging
import pandas as pd
from typing import Tuple

logger = logging.getLogger(__name__)


class DealsDeduplicator:
    """Handles deduplication of deals across NSE and BSE exchanges."""
    
    @staticmethod
    def normalize_for_comparison(value) -> str:
        """
        Normalize value for comparison (lowercase, strip whitespace).
        
        Args:
            value: Value to normalize
            
        Returns:
            Normalized string
        """
        if pd.isna(value) or value is None:
            return ""
        return str(value).lower().strip()
    
    @staticmethod
    def create_match_key(row: pd.Series) -> str:
        """
        Create a composite key for matching duplicates.
        
        Match criteria:
        - Symbol/Security Name (normalized)
        - Client Name (normalized)
        - Deal Type
        - Quantity
        - Price (rounded to 4 decimal places)
        - Date
        
        Args:
            row: DataFrame row
            
        Returns:
            Composite match key
        """
        symbol = DealsDeduplicator.normalize_for_comparison(row.get('symbol', ''))
        client = DealsDeduplicator.normalize_for_comparison(row.get('client_name', ''))
        deal_type = str(row.get('deal_type', '')).upper()
        quantity = int(row.get('quantity', 0)) if pd.notna(row.get('quantity')) else 0
        
        # Price to 4dp for matching
        try:
            price = float(row.get('price', 0))
            price_str = f"{price:.4f}"
        except (ValueError, TypeError):
            price_str = "0.0000"
        
        date = str(row.get('date', ''))
        
        # Composite key
        return f"{symbol}|{client}|{deal_type}|{quantity}|{price_str}|{date}"
    
    @staticmethod
    def deduplicate(combined_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Deduplicate deals across exchanges.
        
        Priority: BSE records are kept, NSE duplicates are removed.
        
        Args:
            combined_df: DataFrame with all deals (NSE + BSE)
            
        Returns:
            Tuple of (deduplicated_df, removed_duplicates_df)
        """
        if combined_df.empty:
            logger.info("No data to deduplicate")
            return combined_df, pd.DataFrame()
        
        logger.info(f"Starting deduplication on {len(combined_df)} total deals")
        
        # Create match keys for all records
        combined_df['_match_key'] = combined_df.apply(
            DealsDeduplicator.create_match_key, 
            axis=1
        )
        
        # Separate NSE and BSE
        nse_df = combined_df[combined_df['exchange'] == 'NSE'].copy()
        bse_df = combined_df[combined_df['exchange'] == 'BSE'].copy()
        
        logger.info(f"NSE records: {len(nse_df)}, BSE records: {len(bse_df)}")
        
        # Find NSE records that have matching BSE records
        bse_keys = set(bse_df['_match_key'].values)
        nse_duplicates = nse_df[nse_df['_match_key'].isin(bse_keys)].copy()
        nse_unique = nse_df[~nse_df['_match_key'].isin(bse_keys)].copy()
        
        logger.info(f"Found {len(nse_duplicates)} NSE duplicates (matched with BSE)")
        logger.info(f"Keeping {len(nse_unique)} unique NSE records")
        logger.info(f"Keeping all {len(bse_df)} BSE records")
        
        # Log some examples of removed duplicates
        if not nse_duplicates.empty:
            logger.info("Sample removed duplicates:")
            for idx, row in nse_duplicates.head(5).iterrows():
                logger.info(
                    f"  Removed NSE: {row['symbol']} | {row['client_name']} | "
                    f"{row['deal_type']} | {row['quantity']} @ {row['price']}"
                )
        
        # Combine unique records (all BSE + unique NSE)
        deduplicated = pd.concat([bse_df, nse_unique], ignore_index=True)
        
        # Remove the temporary match key column
        deduplicated = deduplicated.drop(columns=['_match_key'])
        removed = nse_duplicates.drop(columns=['_match_key'])
        
        logger.info(f"Deduplication complete: {len(combined_df)} → {len(deduplicated)} deals")
        logger.info(f"Removed {len(removed)} duplicate NSE records")
        
        return deduplicated, removed
    
    @staticmethod
    def find_internal_duplicates(df: pd.DataFrame) -> pd.DataFrame:
        """
        Find duplicates within the same exchange (potential data quality issues).
        
        Args:
            df: DataFrame to check
            
        Returns:
            DataFrame with duplicate records
        """
        if df.empty:
            return pd.DataFrame()
        
        df['_match_key'] = df.apply(DealsDeduplicator.create_match_key, axis=1)
        
        # Find duplicates
        duplicated_keys = df[df.duplicated(subset=['_match_key'], keep=False)].copy()
        
        if not duplicated_keys.empty:
            logger.warning(f"Found {len(duplicated_keys)} internal duplicates!")
            for key in duplicated_keys['_match_key'].unique():
                dups = duplicated_keys[duplicated_keys['_match_key'] == key]
                logger.warning(f"  Duplicate group ({len(dups)} records):")
                for idx, row in dups.iterrows():
                    logger.warning(
                        f"    {row['exchange']} | {row['symbol']} | {row['client_name']} | "
                        f"{row['deal_type']} | {row['quantity']} @ {row['price']}"
                    )
        
        return duplicated_keys.drop(columns=['_match_key'])
