#!/usr/bin/env python3
"""
Redis Connection Test - Debug Docker networking issues
"""

import os
import sys
import time
import redis

def test_redis_connection():
    """Test Redis connection with detailed debugging"""
    print("🔍 Redis Connection Debug Test")
    print("=" * 50)
    
    # Show environment variables
    print("Environment Variables:")
    redis_vars = ['REDIS_HOST', 'REDIS_PORT', 'REDIS_URL', 'REDIS_DB', 'REDIS_PASSWORD']
    for var in redis_vars:
        value = os.getenv(var, 'NOT_SET')
        print(f"  {var}: {value}")
    
    print("\nConnection Tests:")
    print("-" * 30)
    
    # Test 1: Direct connection with environment variables
    print("🧪 Test 1: Environment-based connection")
    try:
        host = os.getenv('REDIS_HOST', 'localhost')
        port = int(os.getenv('REDIS_PORT', 6379))
        
        client = redis.Redis(
            host=host,
            port=port,
            db=int(os.getenv('REDIS_DB', 0)),
            socket_connect_timeout=5,
            socket_timeout=5,
            decode_responses=True
        )
        
        client.ping()
        print(f"✅ SUCCESS: Connected to Redis at {host}:{port}")
        
        # Test basic operations
        client.set('test_key', 'test_value')
        value = client.get('test_key')
        client.delete('test_key')
        print(f"✅ Basic operations work: set/get/delete")
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Test 2: Try localhost fallback
    print("\n🧪 Test 2: Localhost fallback")
    try:
        client = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            socket_connect_timeout=5,
            socket_timeout=5,
            decode_responses=True
        )
        
        client.ping()
        print("✅ SUCCESS: Connected to localhost:6379")
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Test 3: Try Redis container name
    print("\n🧪 Test 3: Redis container name")
    try:
        client = redis.Redis(
            host='redis',
            port=6379,
            db=0,
            socket_connect_timeout=5,
            socket_timeout=5,
            decode_responses=True
        )
        
        client.ping()
        print("✅ SUCCESS: Connected to redis:6379")
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Test 4: Try backfin-redis container name
    print("\n🧪 Test 4: Full container name")
    try:
        client = redis.Redis(
            host='backfin-redis',
            port=6379,
            db=0,
            socket_connect_timeout=5,
            socket_timeout=5,
            decode_responses=True
        )
        
        client.ping()
        print("✅ SUCCESS: Connected to backfin-redis:6379")
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Test 5: Using RedisConfig class
    print("\n🧪 Test 5: Using RedisConfig class")
    try:
        sys.path.append('/app')  # Ensure we can import from the app
        from src.queue.redis_client import RedisConfig
        
        config = RedisConfig()
        client = config.get_connection()
        print("✅ SUCCESS: RedisConfig class works")
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    test_redis_connection()