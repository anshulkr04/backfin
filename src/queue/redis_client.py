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
        
    def get_connection(self) -> Redis:
        """Get Redis connection with connection pooling"""
        try:
            if self.redis_url:
                return redis.from_url(
                    self.redis_url,
                    max_connections=self.max_connections,
                    socket_connect_timeout=self.socket_connect_timeout,
                    socket_timeout=self.socket_timeout
                )
            else:
                return redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    db=self.redis_db,
                    password=self.redis_password,
                    max_connections=self.max_connections,
                    socket_connect_timeout=self.socket_connect_timeout,
                    socket_timeout=self.socket_timeout
                )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}")

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