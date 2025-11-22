#!/usr/bin/env python3
"""
Utility functions for deals management system.
"""

import re
import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

logger = logging.getLogger(__name__)


def parse_date_to_iso(date_str: str) -> Optional[str]:
    """
    Convert various date formats to ISO format (YYYY-MM-DD).
    
    Supports:
    - '30-SEP-2025' (NSE format)
    - '30-09-2025' 
    - '23/10/2025' (BSE format)
    - '30/09/2025'
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        ISO date string (YYYY-MM-DD) or None if parsing fails
    """
    if not date_str:
        return None
        
    formats = [
        "%d-%b-%Y",  # 30-SEP-2025
        "%d-%m-%Y",  # 30-09-2025
        "%d/%m/%Y",  # 23/10/2025
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    
    logger.warning(f"Failed to parse date: {date_str}")
    return None


def parse_price_to_4dp(value) -> Optional[str]:
    """
    Parse price value to 4 decimal places.
    
    Args:
        value: Price value (string, number, or None)
        
    Returns:
        Price as string with 4 decimal places, or None
    """
    if value is None or value == "":
        return None
        
    try:
        # Remove any commas or non-numeric characters except decimal point
        cleaned = re.sub(r"[^\d.]", "", str(value))
        d = Decimal(cleaned)
        d = d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return str(d)
    except Exception as e:
        logger.warning(f"Failed to parse price '{value}': {e}")
        return None


def parse_quantity(value) -> Optional[int]:
    """
    Parse quantity value to integer.
    
    Args:
        value: Quantity value (string, number, or None)
        
    Returns:
        Quantity as integer, or None
    """
    if value is None or value == "":
        return None
        
    try:
        # Remove commas and any non-digit characters
        cleaned = re.sub(r"[^\d]", "", str(value))
        return int(cleaned) if cleaned else None
    except Exception as e:
        logger.warning(f"Failed to parse quantity '{value}': {e}")
        return None


def normalize_deal_type(deal_type: str) -> Optional[str]:
    """
    Normalize deal type to standard format.
    
    Args:
        deal_type: Raw deal type (B/S/BUY/SELL/Buy/Sell)
        
    Returns:
        'BUY' or 'SELL', or None
    """
    if not deal_type:
        return None
        
    normalized = deal_type.strip().upper()
    
    if normalized in ('B', 'BUY'):
        return 'BUY'
    elif normalized in ('S', 'SELL'):
        return 'SELL'
    else:
        logger.warning(f"Unknown deal type: {deal_type}")
        return None


def clean_symbol(symbol: str) -> Optional[str]:
    """
    Clean and normalize symbol/security name.
    
    Args:
        symbol: Raw symbol or security name
        
    Returns:
        Cleaned symbol or None
    """
    if not symbol:
        return None
        
    # Remove extra whitespace
    cleaned = ' '.join(symbol.strip().split())
    
    return cleaned if cleaned else None


def normalize_security_code(code: str) -> Optional[str]:
    """
    Normalize security code (remove leading zeros, clean format).
    
    Args:
        code: Raw security code
        
    Returns:
        Normalized code or None
    """
    if not code:
        return None
        
    # Remove any non-alphanumeric characters
    cleaned = re.sub(r"[^\w]", "", str(code).strip())
    
    return cleaned if cleaned else None
