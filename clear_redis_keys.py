#!/usr/bin/env python3
"""
Clear Redis queued keys to allow reprocessing of announcements
"""

import redis
import os

def clear_queued_keys():
    """Clear all queued announcement keys from Redis"""
    try:
        # Connect to Redis
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        
        r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        
        # Find all queued keys
        pattern = "backfin:ann:queued:*"
        keys = r.keys(pattern)
        
        if keys:
            print(f"Found {len(keys)} queued keys to delete")
            
            # Delete keys in batches
            batch_size = 100
            deleted_count = 0
            
            for i in range(0, len(keys), batch_size):
                batch = keys[i:i + batch_size]
                deleted = r.delete(*batch)
                deleted_count += deleted
                print(f"Deleted batch {i//batch_size + 1}: {deleted} keys")
            
            print(f"Total deleted: {deleted_count} keys")
        else:
            print("No queued keys found")
            
    except Exception as e:
        print(f"Error clearing Redis keys: {e}")

if __name__ == "__main__":
    clear_queued_keys()