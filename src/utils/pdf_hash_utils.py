"""
PDF Hash Utilities for Duplicate Detection

This module provides utilities for calculating and managing PDF file hashes
to detect duplicate announcements from the same company.

Usage:
    from src.utils.pdf_hash_utils import calculate_pdf_hash, check_pdf_duplicate
    
    # Calculate hash
    pdf_hash, file_size = calculate_pdf_hash('/path/to/file.pdf')
    
    # Check if duplicate
    is_dup, original_data = check_pdf_duplicate(supabase, 'INE123A01012', pdf_hash)
"""

import hashlib
import os
import logging
from typing import Tuple, Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


def calculate_pdf_hash(filepath: str, chunk_size: int = 8192) -> Tuple[Optional[str], Optional[int]]:
    """
    Calculate SHA-256 hash of a PDF file.
    
    Args:
        filepath: Path to the PDF file
        chunk_size: Size of chunks to read (default: 8KB)
        
    Returns:
        Tuple of (hash_string, file_size_bytes) or (None, None) on error
        
    Example:
        >>> pdf_hash, size = calculate_pdf_hash('/tmp/announcement.pdf')
        >>> print(f"Hash: {pdf_hash}, Size: {size} bytes")
    """
    if not filepath or not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return None, None
    
    try:
        file_size = os.path.getsize(filepath)
        sha256_hash = hashlib.sha256()
        
        with open(filepath, 'rb') as f:
            # Read file in chunks to handle large files efficiently
            while chunk := f.read(chunk_size):
                sha256_hash.update(chunk)
        
        hash_string = sha256_hash.hexdigest()
        logger.info(f"✅ Calculated PDF hash: {hash_string[:16]}... (size: {file_size} bytes)")
        
        return hash_string, file_size
        
    except Exception as e:
        logger.error(f"❌ Error calculating PDF hash for {filepath}: {e}")
        return None, None


def check_pdf_duplicate(
    supabase, 
    isin: str, 
    pdf_hash: str,
    symbol: Optional[str] = None
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Check if a PDF hash already exists for a company.
    
    Args:
        supabase: Supabase client instance
        isin: Company ISIN code
        pdf_hash: SHA-256 hash of the PDF
        symbol: Optional stock symbol for logging
        
    Returns:
        Tuple of (is_duplicate, original_data)
        - is_duplicate: Boolean indicating if PDF is a duplicate
        - original_data: Dict with original announcement info if duplicate, else None
            {
                'original_corp_id': UUID,
                'original_newsid': str,
                'duplicate_count': int,
                'first_seen_at': timestamp
            }
            
    Example:
        >>> is_dup, orig = check_pdf_duplicate(supabase, 'INE123A01012', 'abc123...')
        >>> if is_dup:
        ...     print(f"Duplicate of {orig['original_corp_id']}")
    """
    if not supabase or not isin or not pdf_hash:
        logger.warning("Missing required parameters for duplicate check")
        return False, None
    
    try:
        # Query the hash tracking table
        response = supabase.table('announcement_pdf_hashes')\
            .select('original_corp_id, original_newsid, duplicate_count, first_seen_at')\
            .eq('isin', isin)\
            .eq('pdf_hash', pdf_hash)\
            .limit(1)\
            .execute()
        
        if response.data and len(response.data) > 0:
            original_data = response.data[0]
            logger.info(
                f"🔍 Duplicate PDF detected for {isin} (symbol: {symbol}): "
                f"Original corp_id={original_data['original_corp_id']}, "
                f"duplicates={original_data['duplicate_count']}"
            )
            return True, original_data
        else:
            logger.info(f"✅ New unique PDF for {isin} (symbol: {symbol})")
            return False, None
            
    except Exception as e:
        logger.error(f"❌ Error checking PDF duplicate: {e}")
        # On error, treat as non-duplicate to avoid blocking processing
        return False, None


def register_pdf_hash(
    supabase,
    announcement_data: Dict[str, Any],
    pdf_hash: str,
    pdf_size: int
) -> bool:
    """
    Register a new PDF hash in the tracking table.
    
    Args:
        supabase: Supabase client instance
        announcement_data: Dict containing announcement details
            Required keys: corp_id, isin, symbol, companyname, date, newsid
        pdf_hash: SHA-256 hash of the PDF
        pdf_size: File size in bytes
        
    Returns:
        True if registration successful, False otherwise
        
    Example:
        >>> data = {
        ...     'corp_id': 'uuid-here',
        ...     'isin': 'INE123A01012',
        ...     'symbol': 'RELIANCE',
        ...     'companyname': 'Reliance Industries',
        ...     'date': '2026-01-14T10:00:00',
        ...     'newsid': 'BSE123456'
        ... }
        >>> success = register_pdf_hash(supabase, data, 'abc123...', 102400)
    """
    try:
        hash_data = {
            'pdf_hash': pdf_hash,
            'pdf_size_bytes': pdf_size,
            'isin': announcement_data.get('isin'),
            'symbol': announcement_data.get('symbol'),
            'company_name': announcement_data.get('companyname'),
            'original_corp_id': announcement_data.get('corp_id'),
            'original_newsid': announcement_data.get('newsid'),
            'original_date': announcement_data.get('date'),
            'duplicate_count': 0
        }
        
        # Insert into tracking table
        response = supabase.table('announcement_pdf_hashes').insert(hash_data).execute()
        
        if response.data:
            logger.info(
                f"📝 Registered PDF hash for {announcement_data.get('symbol')} "
                f"(corp_id={announcement_data.get('corp_id')})"
            )
            return True
        else:
            logger.warning(f"Failed to register PDF hash: No data returned")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error registering PDF hash: {e}")
        # Check if it's a duplicate key error (hash already exists)
        if "duplicate key" in str(e).lower() or "23505" in str(e):
            logger.info("Hash already registered (duplicate key), continuing...")
            return True  # Not a failure, just already exists
        return False


def mark_announcement_duplicate(
    supabase,
    corp_id: str,
    original_corp_id: str,
    original_newsid: str,
    pdf_hash: str,
    pdf_size: int
) -> bool:
    """
    Mark an announcement as a duplicate.
    
    Args:
        supabase: Supabase client instance
        corp_id: Corp ID of the duplicate announcement
        original_corp_id: Corp ID of the original announcement
        original_newsid: News ID of the original announcement
        pdf_hash: SHA-256 hash of the PDF
        pdf_size: File size in bytes
        
    Returns:
        True if marking successful, False otherwise
        
    Example:
        >>> success = mark_announcement_duplicate(
        ...     supabase,
        ...     corp_id='duplicate-uuid',
        ...     original_corp_id='original-uuid',
        ...     original_newsid='BSE123456',
        ...     pdf_hash='abc123...',
        ...     pdf_size=102400
        ... )
    """
    try:
        update_data = {
            'is_duplicate': True,
            'original_announcement_id': original_corp_id,
            'duplicate_of_newsid': original_newsid,
            'pdf_hash': pdf_hash,
            'pdf_size_bytes': pdf_size
        }
        
        # Update the announcement record
        response = supabase.table('corporatefilings')\
            .update(update_data)\
            .eq('corp_id', corp_id)\
            .execute()
        
        if response.data:
            logger.info(
                f"🔄 Marked announcement {corp_id} as duplicate of {original_corp_id}"
            )
            return True
        else:
            logger.warning(f"Failed to mark announcement as duplicate: No data returned")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error marking announcement as duplicate: {e}")
        return False


def update_announcement_hash(
    supabase,
    corp_id: str,
    pdf_hash: str,
    pdf_size: int
) -> bool:
    """
    Update an announcement with its PDF hash (for non-duplicate original announcements).
    
    Args:
        supabase: Supabase client instance
        corp_id: Corp ID of the announcement
        pdf_hash: SHA-256 hash of the PDF
        pdf_size: File size in bytes
        
    Returns:
        True if update successful, False otherwise
    """
    try:
        update_data = {
            'pdf_hash': pdf_hash,
            'pdf_size_bytes': pdf_size,
            'is_duplicate': False  # Explicitly mark as not duplicate
        }
        
        response = supabase.table('corporatefilings')\
            .update(update_data)\
            .eq('corp_id', corp_id)\
            .execute()
        
        if response.data:
            logger.info(f"📝 Updated announcement {corp_id} with PDF hash")
            return True
        else:
            logger.warning(f"Failed to update announcement hash: No data returned")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error updating announcement hash: {e}")
        return False


def process_pdf_for_duplicates(
    supabase,
    pdf_filepath: str,
    announcement_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Complete workflow: Calculate hash, check for duplicates, and handle accordingly.
    
    This is the main function to call during announcement processing.
    
    Args:
        supabase: Supabase client instance
        pdf_filepath: Path to the downloaded PDF file
        announcement_data: Dict containing announcement details
            Required keys: corp_id, isin, symbol, companyname, date, newsid
            
    Returns:
        Dict with processing results:
        {
            'is_duplicate': bool,
            'pdf_hash': str,
            'pdf_size': int,
            'original_corp_id': str (if duplicate),
            'original_newsid': str (if duplicate),
            'action_taken': str  # 'marked_duplicate', 'registered_new', or 'error'
        }
        
    Example:
        >>> result = process_pdf_for_duplicates(
        ...     supabase,
        ...     '/tmp/announcement.pdf',
        ...     {'corp_id': 'uuid', 'isin': 'INE123A01012', ...}
        ... )
        >>> if result['is_duplicate']:
        ...     print(f"Duplicate of {result['original_corp_id']}")
        ... else:
        ...     print("New unique announcement")
    """
    result = {
        'is_duplicate': False,
        'pdf_hash': None,
        'pdf_size': None,
        'original_corp_id': None,
        'original_newsid': None,
        'action_taken': 'error'
    }
    
    try:
        # Step 1: Calculate PDF hash
        pdf_hash, pdf_size = calculate_pdf_hash(pdf_filepath)
        
        if not pdf_hash:
            logger.error("Failed to calculate PDF hash")
            return result
        
        result['pdf_hash'] = pdf_hash
        result['pdf_size'] = pdf_size
        
        # Step 2: Check for duplicates
        isin = announcement_data.get('isin')
        symbol = announcement_data.get('symbol')
        corp_id = announcement_data.get('corp_id')
        
        if not isin or not corp_id:
            logger.error("Missing required fields: isin or corp_id")
            return result
        
        is_duplicate, original_data = check_pdf_duplicate(supabase, isin, pdf_hash, symbol)
        
        if is_duplicate and original_data:
            # Step 3a: Mark as duplicate
            result['is_duplicate'] = True
            result['original_corp_id'] = original_data['original_corp_id']
            result['original_newsid'] = original_data['original_newsid']
            
            success = mark_announcement_duplicate(
                supabase,
                corp_id,
                original_data['original_corp_id'],
                original_data['original_newsid'],
                pdf_hash,
                pdf_size
            )
            
            result['action_taken'] = 'marked_duplicate' if success else 'error'
            
        else:
            # Step 3b: Register new hash and update announcement
            result['is_duplicate'] = False
            
            # Register in hash tracking table
            register_success = register_pdf_hash(
                supabase,
                announcement_data,
                pdf_hash,
                pdf_size
            )
            
            # Update announcement with hash
            update_success = update_announcement_hash(
                supabase,
                corp_id,
                pdf_hash,
                pdf_size
            )
            
            result['action_taken'] = 'registered_new' if (register_success and update_success) else 'error'
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error in process_pdf_for_duplicates: {e}")
        return result


def get_duplicate_stats(supabase, isin: Optional[str] = None) -> Dict[str, Any]:
    """
    Get duplicate detection statistics.
    
    Args:
        supabase: Supabase client instance
        isin: Optional ISIN to filter statistics for specific company
        
    Returns:
        Dict with statistics:
        {
            'total_hashes': int,
            'total_duplicates': int,
            'companies_affected': int,
            'top_duplicates': List[Dict]  # Companies with most duplicates
        }
    """
    try:
        stats = {
            'total_hashes': 0,
            'total_duplicates': 0,
            'companies_affected': 0,
            'top_duplicates': []
        }
        
        # Query hash table
        query = supabase.table('announcement_pdf_hashes').select('*')
        
        if isin:
            query = query.eq('isin', isin)
        
        response = query.execute()
        
        if response.data:
            stats['total_hashes'] = len(response.data)
            stats['total_duplicates'] = sum(item['duplicate_count'] for item in response.data)
            stats['companies_affected'] = len(set(item['isin'] for item in response.data))
            
            # Top duplicates
            sorted_data = sorted(response.data, key=lambda x: x['duplicate_count'], reverse=True)
            stats['top_duplicates'] = sorted_data[:10]
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting duplicate stats: {e}")
        return {
            'total_hashes': 0,
            'total_duplicates': 0,
            'companies_affected': 0,
            'top_duplicates': [],
            'error': str(e)
        }


# Convenience function for backward compatibility
def should_process_announcement(supabase, isin: str, pdf_hash: str) -> bool:
    """
    Simple yes/no check: Should this announcement be processed normally?
    
    Returns:
        True if announcement is unique (not a duplicate)
        False if announcement is a duplicate
    """
    is_duplicate, _ = check_pdf_duplicate(supabase, isin, pdf_hash)
    return not is_duplicate


if __name__ == "__main__":
    # Example usage and testing
    import sys
    from dotenv import load_dotenv
    from supabase import create_client
    
    load_dotenv()
    
    # Initialize Supabase client
    SUPABASE_URL = os.getenv('SUPABASE_URL2')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY2')
    
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Test hash calculation
        if len(sys.argv) > 1:
            test_file = sys.argv[1]
            if os.path.exists(test_file):
                pdf_hash, pdf_size = calculate_pdf_hash(test_file)
                print(f"\nPDF Hash: {pdf_hash}")
                print(f"File Size: {pdf_size} bytes")
                
                # Test duplicate check (if ISIN provided)
                if len(sys.argv) > 2:
                    test_isin = sys.argv[2]
                    is_dup, orig_data = check_pdf_duplicate(supabase, test_isin, pdf_hash)
                    print(f"\nIs Duplicate: {is_dup}")
                    if is_dup:
                        print(f"Original Data: {orig_data}")
            else:
                print(f"File not found: {test_file}")
        else:
            print("Usage: python pdf_hash_utils.py <pdf_file> [isin]")
            print("\nExample:")
            print("  python pdf_hash_utils.py /path/to/file.pdf INE123A01012")
    else:
        print("Error: Supabase credentials not found in environment")
