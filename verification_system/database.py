"""
Database utilities and Supabase client management
"""
import logging
from typing import Optional
from supabase import create_client, Client
from config import settings

logger = logging.getLogger(__name__)

class Database:
    """Supabase database client manager"""
    
    def __init__(self):
        self._client: Optional[Client] = None
        
    def connect(self) -> Client:
        """Initialize and return Supabase client"""
        if self._client is None:
            try:
                self._client = create_client(
                    settings.SUPABASE_URL2,
                    settings.SUPABASE_SERVICE_ROLE_KEY
                )
                logger.info("✅ Connected to Supabase")
            except Exception as e:
                logger.error(f"❌ Failed to connect to Supabase: {e}")
                raise
        return self._client
    
    def get_client(self) -> Client:
        """Get existing client or create new one"""
        if self._client is None:
            return self.connect()
        return self._client
    
    def disconnect(self):
        """Cleanup connection"""
        self._client = None
        logger.info("Disconnected from Supabase")

# Global database instance
db = Database()

def get_db() -> Client:
    """Dependency for FastAPI routes"""
    return db.get_client()
