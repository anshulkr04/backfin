#!/usr/bin/env python3
"""
Backfill Classification Comparison

This script processes existing announcements in the database and runs
Gemma 3 27B classification to compare with the existing Gemini classifications.

Usage:
    python backfill_classification_comparison.py --limit 100
    python backfill_classification_comparison.py --limit 500 --delay 3
    python backfill_classification_comparison.py --start-date 2025-01-01 --end-date 2025-02-01
"""

import os
import sys
import logging
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from supabase import create_client
from src.ai.gemma_classifier import run_parallel_classification, GemmaClassifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_supabase_client():
    """Initialize and return Supabase client."""
    supabase_url = os.getenv('SUPABASE_URL2')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL2 and SUPABASE_SERVICE_ROLE_KEY must be set")
    
    return create_client(supabase_url, supabase_key)


def get_announcements_to_process(
    supabase,
    limit: int = 100,
    start_date: str = None,
    end_date: str = None,
    exclude_processed: bool = True
):
    """
    Get announcements that need Gemma classification.
    
    Args:
        supabase: Supabase client
        limit: Maximum number of announcements to retrieve
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)
        exclude_processed: Skip announcements already in comparison table
        
    Returns:
        List of announcement dictionaries
    """
    # Build query
    query = supabase.table('corporatefilings')\
        .select('corp_id, category, ai_summary, fileurl, isin, symbol, companyname, pdf_hash, date')\
        .not_.is_('fileurl', 'null')\
        .not_.is_('category', 'null')
    
    # Add date filters
    if start_date:
        query = query.gte('date', start_date)
    if end_date:
        query = query.lte('date', end_date)
    
    # Order and limit
    query = query.order('date', desc=True).limit(limit * 2 if exclude_processed else limit)
    
    response = query.execute()
    
    if not response.data:
        return []
    
    announcements = response.data
    
    # Exclude already processed if requested
    if exclude_processed:
        try:
            existing = supabase.table('classification_comparison')\
                .select('corp_id')\
                .execute()
            
            processed_ids = set(row['corp_id'] for row in (existing.data or []))
            
            announcements = [
                ann for ann in announcements 
                if ann['corp_id'] not in processed_ids
            ][:limit]
            
        except Exception as e:
            logger.warning(f"Could not check existing comparisons: {e}")
    
    return announcements


def process_announcement(supabase, announcement: dict, gemma_api_key: str = None) -> dict:
    """
    Process a single announcement with Gemma classification.
    
    Args:
        supabase: Supabase client
        announcement: Announcement data dictionary
        gemma_api_key: Optional API key for Gemma
        
    Returns:
        Result dictionary with comparison info
    """
    result = {
        "corp_id": announcement.get('corp_id'),
        "success": False,
        "match": None,
        "gemini_category": announcement.get('category'),
        "gemma_category": None,
        "error": None
    }
    
    try:
        gemma_result = run_parallel_classification(
            pdf_url=announcement.get('fileurl'),
            gemini_category=announcement.get('category', 'Unknown'),
            gemini_summary=announcement.get('ai_summary'),
            supabase=supabase,
            corp_id=announcement.get('corp_id'),
            pdf_hash=announcement.get('pdf_hash'),
            isin=announcement.get('isin'),
            symbol=announcement.get('symbol'),
            company_name=announcement.get('companyname'),
            gemma_api_key=gemma_api_key
        )
        
        result["gemma_category"] = gemma_result.get('gemma_category')
        result["match"] = gemma_result.get('categories_match')
        result["success"] = gemma_result.get('comparison_stored', False)
        
        if gemma_result.get('error'):
            result["error"] = gemma_result['error']
            
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Error processing {announcement.get('corp_id')}: {e}")
    
    return result


def run_backfill(
    limit: int = 100,
    delay: float = 2.0,
    start_date: str = None,
    end_date: str = None,
    gemma_api_key: str = None,
    dry_run: bool = False
):
    """
    Run the backfill process.
    
    Args:
        limit: Maximum number of announcements to process
        delay: Delay between API calls in seconds
        start_date: Optional start date filter
        end_date: Optional end date filter
        gemma_api_key: Optional API key for Gemma
        dry_run: If True, just list what would be processed
    """
    logger.info("=" * 60)
    logger.info("Starting Classification Comparison Backfill")
    logger.info("=" * 60)
    
    # Initialize clients
    try:
        supabase = get_supabase_client()
        logger.info("✅ Supabase client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Supabase: {e}")
        return
    
    # Verify Gemma classifier is available
    if not dry_run:
        classifier = GemmaClassifier(api_key=gemma_api_key)
        if not classifier.client:
            logger.error("❌ Gemma classifier could not be initialized. Check your API key.")
            return
        logger.info("✅ Gemma classifier initialized")
    
    # Get announcements to process
    logger.info(f"📊 Fetching announcements (limit: {limit})")
    if start_date:
        logger.info(f"   Start date: {start_date}")
    if end_date:
        logger.info(f"   End date: {end_date}")
    
    announcements = get_announcements_to_process(
        supabase,
        limit=limit,
        start_date=start_date,
        end_date=end_date
    )
    
    if not announcements:
        logger.info("No announcements to process")
        return
    
    logger.info(f"📋 Found {len(announcements)} announcements to process")
    
    if dry_run:
        logger.info("\n🔍 DRY RUN - Would process these announcements:")
        for i, ann in enumerate(announcements[:20], 1):
            logger.info(f"   {i}. {ann.get('corp_id')[:8]}... | {ann.get('symbol')} | {ann.get('category')}")
        if len(announcements) > 20:
            logger.info(f"   ... and {len(announcements) - 20} more")
        return
    
    # Process announcements
    stats = {
        "processed": 0,
        "success": 0,
        "errors": 0,
        "matches": 0,
        "mismatches": 0
    }
    
    start_time = time.time()
    
    for i, ann in enumerate(announcements, 1):
        logger.info(f"\n📄 [{i}/{len(announcements)}] Processing {ann.get('symbol')} - {ann.get('category')}")
        
        result = process_announcement(supabase, ann, gemma_api_key)
        stats["processed"] += 1
        
        if result["success"]:
            stats["success"] += 1
            if result["match"] is True:
                stats["matches"] += 1
                logger.info(f"   ✅ MATCH - Both classified as: {result['gemini_category']}")
            elif result["match"] is False:
                stats["mismatches"] += 1
                logger.info(f"   ❌ MISMATCH - Gemini: {result['gemini_category']} | Gemma: {result['gemma_category']}")
            else:
                logger.info(f"   ⚠️ Comparison stored but match status unknown")
        else:
            stats["errors"] += 1
            logger.warning(f"   ⚠️ Failed: {result.get('error', 'Unknown error')}")
        
        # Progress update every 10 announcements
        if i % 10 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed
            remaining = (len(announcements) - i) / rate if rate > 0 else 0
            logger.info(f"\n📊 Progress: {i}/{len(announcements)} | "
                       f"Success: {stats['success']} | Errors: {stats['errors']} | "
                       f"Match rate: {100*stats['matches']/max(1,stats['success']):.1f}% | "
                       f"ETA: {remaining/60:.1f} min")
        
        # Rate limiting
        if i < len(announcements):
            time.sleep(delay)
    
    # Final summary
    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 60)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 60)
    logger.info(f"📊 Total processed: {stats['processed']}")
    logger.info(f"✅ Successful: {stats['success']}")
    logger.info(f"❌ Errors: {stats['errors']}")
    logger.info(f"🎯 Matches: {stats['matches']}")
    logger.info(f"⚡ Mismatches: {stats['mismatches']}")
    if stats['success'] > 0:
        match_rate = 100 * stats['matches'] / stats['success']
        logger.info(f"📈 Match rate: {match_rate:.1f}%")
    logger.info(f"⏱️ Total time: {elapsed/60:.1f} minutes")
    logger.info(f"🚀 Average rate: {stats['processed']/elapsed*60:.1f} announcements/minute")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill Gemma classification for existing announcements"
    )
    
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=100,
        help="Maximum number of announcements to process (default: 100)"
    )
    
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=2.0,
        help="Delay between API calls in seconds (default: 2.0)"
    )
    
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date filter (YYYY-MM-DD)"
    )
    
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date filter (YYYY-MM-DD)"
    )
    
    parser.add_argument(
        "--api-key",
        type=str,
        help="Gemma API key (uses GEMMA_API_KEY or GEMINI_API_KEY env var if not provided)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Just list what would be processed without actually processing"
    )
    
    args = parser.parse_args()
    
    run_backfill(
        limit=args.limit,
        delay=args.delay,
        start_date=args.start_date,
        end_date=args.end_date,
        gemma_api_key=args.api_key,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
