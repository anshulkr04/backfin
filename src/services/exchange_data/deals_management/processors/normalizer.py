#!/usr/bin/env python3
"""
Data normalizer - Converts raw NSE/BSE data to standardized format.
"""

import logging
import pandas as pd
from typing import List, Dict, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.helpers import (
    parse_date_to_iso,
    parse_price_to_4dp,
    parse_quantity,
    normalize_deal_type,
    clean_symbol,
    normalize_security_code
)

logger = logging.getLogger(__name__)


class DataNormalizer:
    """Normalizes raw NSE and BSE deal data to standardized format."""
    
    @staticmethod
    def normalize_nse_bulk(records: List[Dict]) -> pd.DataFrame:
        """
        Normalize NSE bulk deals to standard format.
        
        Args:
            records: List of raw NSE bulk deal records
            
        Returns:
            DataFrame with normalized data
        """
        normalized = []
        
        for record in records:
            try:
                norm_record = {
                    'symbol': clean_symbol(record.get('BD_SYMBOL')),
                    'securityid': None,  # Will be populated by trigger
                    'date': parse_date_to_iso(record.get('BD_DT_DATE', '')),
                    'client_name': clean_symbol(record.get('BD_CLIENT_NAME')),
                    'deal_type': normalize_deal_type(record.get('BD_BUY_SELL')),
                    'quantity': parse_quantity(record.get('BD_QTY_TRD')),
                    'price': parse_price_to_4dp(record.get('BD_TP_WATP')),
                    'exchange': 'NSE',
                    'deal': 'BULK',
                    'source_data': record  # Keep original for debugging
                }
                
                # Only add if essential fields are present
                if all([
                    norm_record['symbol'],
                    norm_record['date'],
                    norm_record['client_name'],
                    norm_record['deal_type'],
                    norm_record['quantity'] is not None,
                    norm_record['price'] is not None
                ]):
                    normalized.append(norm_record)
                else:
                    logger.debug(f"Skipped incomplete NSE bulk record: {record.get('BD_SYMBOL')}")
                    
            except Exception as e:
                logger.warning(f"Error normalizing NSE bulk record: {e}")
                continue
        
        df = pd.DataFrame(normalized)
        logger.info(f"Normalized {len(df)} NSE bulk deals")
        return df
    
    @staticmethod
    def normalize_nse_block(records: List[Dict]) -> pd.DataFrame:
        """
        Normalize NSE block deals to standard format.
        
        Args:
            records: List of raw NSE block deal records
            
        Returns:
            DataFrame with normalized data
        """
        normalized = []
        
        for record in records:
            try:
                norm_record = {
                    'symbol': clean_symbol(record.get('BD_SYMBOL')),
                    'securityid': None,  # Will be populated by trigger
                    'date': parse_date_to_iso(record.get('BD_DT_DATE', '')),
                    'client_name': clean_symbol(record.get('BD_CLIENT_NAME')),
                    'deal_type': normalize_deal_type(record.get('BD_BUY_SELL')),
                    'quantity': parse_quantity(record.get('BD_QTY_TRD')),
                    'price': parse_price_to_4dp(record.get('BD_TP_WATP')),
                    'exchange': 'NSE',
                    'deal': 'BLOCK',
                    'source_data': record
                }
                
                if all([
                    norm_record['symbol'],
                    norm_record['date'],
                    norm_record['client_name'],
                    norm_record['deal_type'],
                    norm_record['quantity'] is not None,
                    norm_record['price'] is not None
                ]):
                    normalized.append(norm_record)
                else:
                    logger.debug(f"Skipped incomplete NSE block record: {record.get('BD_SYMBOL')}")
                    
            except Exception as e:
                logger.warning(f"Error normalizing NSE block record: {e}")
                continue
        
        df = pd.DataFrame(normalized)
        logger.info(f"Normalized {len(df)} NSE block deals")
        return df
    
    @staticmethod
    def normalize_bse_bulk(records: List[Dict]) -> pd.DataFrame:
        """
        Normalize BSE bulk deals to standard format.
        
        Args:
            records: List of raw BSE bulk deal records
            
        Returns:
            DataFrame with normalized data
        """
        normalized = []
        
        for record in records:
            try:
                norm_record = {
                    'symbol': clean_symbol(record.get('Security Name')),
                    'securityid': normalize_security_code(record.get('Security Code')),
                    'date': parse_date_to_iso(record.get('Deal Date', '')),
                    'client_name': clean_symbol(record.get('Client Name')),
                    'deal_type': normalize_deal_type(record.get('Deal Type *')),
                    'quantity': parse_quantity(record.get('Quantity', '')),
                    'price': parse_price_to_4dp(record.get('Price **', '')),
                    'exchange': 'BSE',
                    'deal': 'BULK',
                    'source_data': record
                }
                
                if all([
                    norm_record['symbol'],
                    norm_record['date'],
                    norm_record['client_name'],
                    norm_record['deal_type'],
                    norm_record['quantity'] is not None,
                    norm_record['price'] is not None
                ]):
                    normalized.append(norm_record)
                else:
                    logger.debug(f"Skipped incomplete BSE bulk record: {record.get('Security Name')}")
                    
            except Exception as e:
                logger.warning(f"Error normalizing BSE bulk record: {e}")
                continue
        
        df = pd.DataFrame(normalized)
        logger.info(f"Normalized {len(df)} BSE bulk deals")
        return df
    
    @staticmethod
    def normalize_bse_block(records: List[Dict]) -> pd.DataFrame:
        """
        Normalize BSE block deals to standard format.
        
        Args:
            records: List of raw BSE block deal records
            
        Returns:
            DataFrame with normalized data
        """
        normalized = []
        
        for record in records:
            try:
                norm_record = {
                    'symbol': clean_symbol(record.get('Security Name')),
                    'securityid': normalize_security_code(record.get('Security Code')),
                    'date': parse_date_to_iso(record.get('Deal Date', '')),
                    'client_name': clean_symbol(record.get('Client Name')),
                    'deal_type': normalize_deal_type(record.get('Deal Type *')),
                    'quantity': parse_quantity(record.get('Quantity', '')),
                    'price': parse_price_to_4dp(record.get('Trade Price', '')),
                    'exchange': 'BSE',
                    'deal': 'BLOCK',
                    'source_data': record
                }
                
                if all([
                    norm_record['symbol'],
                    norm_record['date'],
                    norm_record['client_name'],
                    norm_record['deal_type'],
                    norm_record['quantity'] is not None,
                    norm_record['price'] is not None
                ]):
                    normalized.append(norm_record)
                else:
                    logger.debug(f"Skipped incomplete BSE block record: {record.get('Security Name')}")
                    
            except Exception as e:
                logger.warning(f"Error normalizing BSE block record: {e}")
                continue
        
        df = pd.DataFrame(normalized)
        logger.info(f"Normalized {len(df)} BSE block deals")
        return df
