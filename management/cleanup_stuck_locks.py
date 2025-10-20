#!/usr/bin/env python3
"""
Cleanup stuck processing locks
This script removes processing locks that are preventing announcements from being processed
"""

import sys
import logging
import time
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("lock_cleanup")

def cleanup_stuck_locks():
    """Remove stuck processing locks"""
    redis_config = RedisConfig()
    redis_client = redis_config.get_connection()
    
    # Find all processing locks
    processing_locks = redis_client.keys("worker_processing:*")
    queued_locks = redis_client.keys("backfin:ann:queued:*")
    
    logger.info(f"Found {len(processing_locks)} worker processing locks")
    logger.info(f"Found {len(queued_locks)} queued locks")
    
    cleaned_processing = 0
    cleaned_queued = 0
    
    # Clean up worker processing locks
    if processing_locks:
        for lock_key in processing_locks:
            try:
                # Check TTL - if no TTL or expired, remove it
                ttl = redis_client.ttl(lock_key)
                if ttl == -1 or ttl <= 0:  # No TTL or expired
                    redis_client.delete(lock_key)
                    cleaned_processing += 1
                    key_str = lock_key.decode() if isinstance(lock_key, bytes) else lock_key
                    logger.info(f"🔓 Removed stuck processing lock: {key_str}")
            except Exception as e:
                logger.error(f"Error processing lock {lock_key}: {e}")
    
    # Clean up queued locks (these should have been removed when processing completed)
    if queued_locks:
        for lock_key in queued_locks:
            try:
                # These locks often don't have TTL, so check age differently
                # Remove all queued locks as they can be regenerated
                redis_client.delete(lock_key)
                cleaned_queued += 1
                key_str = lock_key.decode() if isinstance(lock_key, bytes) else lock_key
                logger.info(f"🔓 Removed queued lock: {key_str}")
            except Exception as e:
                logger.error(f"Error processing queued lock {lock_key}: {e}")
    
    logger.info(f"✅ Cleanup complete:")
    logger.info(f"   - Removed {cleaned_processing} processing locks")
    logger.info(f"   - Removed {cleaned_queued} queued locks")
    
    return cleaned_processing + cleaned_queued

if __name__ == "__main__":
    cleaned_count = cleanup_stuck_locks()
    print(f"Cleaned up {cleaned_count} stuck locks")