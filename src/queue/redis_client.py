# Redis Configuration for Backfin Queue System

import os
from typing import Optional
import redis
from redis import Redis

class RedisConfig:
    """Redis configuration and connection management"""
    
    def __init__(self):
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        self.redis_password = os.getenv('REDIS_PASSWORD')
        
        # Connection pool settings
        self.max_connections = int(os.getenv('REDIS_MAX_CONNECTIONS', 20))
        self.socket_connect_timeout = int(os.getenv('REDIS_CONNECT_TIMEOUT', 5))
        self.socket_timeout = int(os.getenv('REDIS_SOCKET_TIMEOUT', 5))
        
        # Debug Redis configuration (helpful for Docker troubleshooting)
        print(f"Redis Config: host={self.redis_host}, port={self.redis_port}, url={self.redis_url}")
        print(f"Environment REDIS_HOST: {os.getenv('REDIS_HOST', 'NOT_SET')}")
        print(f"Environment REDIS_PORT: {os.getenv('REDIS_PORT', 'NOT_SET')}")
        
    def get_connection(self) -> Redis:
        """Get Redis connection with connection pooling and retry logic"""
        import time
        
        max_retries = 5
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                if self.redis_url:
                    client = redis.from_url(
                        self.redis_url,
                        max_connections=self.max_connections,
                        socket_connect_timeout=self.socket_connect_timeout,
                        socket_timeout=self.socket_timeout,
                        decode_responses=True
                    )
                else:
                    client = redis.Redis(
                        host=self.redis_host,
                        port=self.redis_port,
                        db=self.redis_db,
                        password=self.redis_password,
                        max_connections=self.max_connections,
                        socket_connect_timeout=self.socket_connect_timeout,
                        socket_timeout=self.socket_timeout,
                        decode_responses=True
                    )
                
                # Test the connection
                client.ping()
                return client
                
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Redis connection attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    raise ConnectionError(f"Failed to connect to Redis after {max_retries} attempts. Last error: {e}")
        
        raise ConnectionError("Unexpected error in Redis connection retry loop")

# Queue Names
class QueueNames:
    """Centralized queue name definitions"""
    NEW_ANNOUNCEMENTS = "backfin:queue:new_announcements"
    AI_PROCESSING = "backfin:queue:ai_processing"  
    SUPABASE_UPLOAD = "backfin:queue:supabase_upload"
    INVESTOR_PROCESSING = "backfin:queue:investor_processing"
    FAILED_JOBS = "backfin:queue:failed_jobs"
    
    # Priority queues
    HIGH_PRIORITY = "backfin:queue:high_priority"
    RETRY_QUEUE = "backfin:queue:retry"
    
    @classmethod
    def all_queues(cls):
        """Get all queue names"""
        return [
            cls.NEW_ANNOUNCEMENTS,
            cls.AI_PROCESSING,
            cls.SUPABASE_UPLOAD,
            cls.INVESTOR_PROCESSING,
            cls.FAILED_JOBS,
            cls.HIGH_PRIORITY,
            cls.RETRY_QUEUE
        ]

# Global Redis instance
redis_config = RedisConfig()
redis_client = redis_config.get_connection()