#!/usr/bin/env python3
"""
Presence Gateway - WebSocket server for verifier connections

Manages verifier presence, heartbeats, and real-time task delivery.
Handles JWT authentication and maintains Redis presence tracking.
"""

import os
import redis
import json
import jwt
import asyncio
import logging
import websockets
from datetime import datetime, timedelta
from typing import Dict, Set, Any, Optional
from websockets.exceptions import ConnectionClosed, WebSocketException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('presence-gateway')

class PresenceGateway:
    def __init__(self):
        # Redis connection
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = None
        
        # JWT configuration
        self.jwt_secret = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
        self.jwt_algorithm = os.getenv('JWT_ALGORITHM', 'HS256')
        
        # WebSocket server configuration
        self.host = os.getenv('PRESENCE_HOST', 'localhost')
        self.port = int(os.getenv('PRESENCE_PORT', 8765))
        
        # Redis keys
        self.active_verifiers_key = 'verifiers:active'
        self.presence_key_template = 'verifier:{}:presence'
        self.capacity_key_template = 'verifier:{}:capacity'
        self.assign_stream_template = 'verif:assign:{}'
        
        # Active connections
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.verifier_ids: Dict[websockets.WebSocketServerProtocol, str] = {}
        
        # Configuration
        self.heartbeat_interval = 5  # seconds
        self.presence_ttl = 10  # seconds
        self.max_verifiers = int(os.getenv('MAX_VERIFIERS', '10'))
        
        # Stats
        self.stats = {
            'connections_total': 0,
            'connections_active': 0,
            'messages_sent': 0,
            'messages_received': 0,
            'heartbeats': 0,
            'acks': 0,
            'started_at': datetime.utcnow().isoformat()
        }
    
    async def connect_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await asyncio.to_thread(self.redis_client.ping)
            logger.info("✅ Connected to Redis")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            return False
    
    def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Verify token has required fields
            if 'verifier_id' not in payload or 'role' not in payload:
                return None
                
            if payload.get('role') != 'verifier':
                return None
                
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("⚠️ JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"⚠️ Invalid JWT token: {e}")
            return None
    
    async def add_verifier_to_presence(self, verifier_id: str):
        """Add verifier to active presence"""
        try:
            # Add to active set
            await asyncio.to_thread(
                self.redis_client.sadd,
                self.active_verifiers_key,
                verifier_id
            )
            
            # Set presence heartbeat with TTL
            presence_key = self.presence_key_template.format(verifier_id)
            await asyncio.to_thread(
                self.redis_client.setex,
                presence_key,
                self.presence_ttl,
                "1"
            )
            
            # Initialize capacity tracking
            capacity_key = self.capacity_key_template.format(verifier_id)
            await asyncio.to_thread(
                self.redis_client.hset,
                capacity_key,
                mapping={
                    'concurrency': '1',
                    'inflight': '0',
                    'last_seen': datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f"👤 Added verifier {verifier_id} to presence")
            
        except Exception as e:
            logger.error(f"❌ Failed to add verifier to presence: {e}")
    
    async def remove_verifier_from_presence(self, verifier_id: str):
        """Remove verifier from active presence"""
        try:
            # Remove from active set
            await asyncio.to_thread(
                self.redis_client.srem,
                self.active_verifiers_key,
                verifier_id
            )
            
            # Remove presence key
            presence_key = self.presence_key_template.format(verifier_id)
            await asyncio.to_thread(
                self.redis_client.delete,
                presence_key
            )
            
            logger.info(f"👤 Removed verifier {verifier_id} from presence")
            
            # Trigger rebalancing (notify dispatcher)
            await self.notify_rebalance_needed()
            
        except Exception as e:
            logger.error(f"❌ Failed to remove verifier from presence: {e}")
    
    async def start_server(self):
        """Start the WebSocket server"""
        logger.info(f"🚀 Starting Presence Gateway on {self.host}:{self.port}")
        
        # Connect to Redis
        if not await self.connect_redis():
            return False
        
        try:
            # Start WebSocket server
            server = await websockets.serve(
                self.handle_verifier_connection,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10
            )
            
            logger.info(f"✅ Presence Gateway running on ws://{self.host}:{self.port}/verifier")
            
            # Keep server running
            await server.wait_closed()
            
        except Exception as e:
            logger.error(f"❌ Failed to start server: {e}")
            return False
        
        return True

async def main():
    """Main entry point"""
    gateway = PresenceGateway()
    await gateway.start_server()

if __name__ == "__main__":
    asyncio.run(main())