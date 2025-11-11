#!/usr/bin/env python3
"""
Redis coordination layer for real-time verification system
"""

import os
import asyncio
import redis.asyncio as redis
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any, Callable
from dataclasses import dataclass
import uuid

logger = logging.getLogger(__name__)

@dataclass
class VerifierPresence:
    session_id: str
    user_id: str
    user_name: str
    connected_at: datetime
    last_heartbeat: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]

class RedisCoordinator:
    def __init__(self):
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = None
        self.pubsub_client = None
        
        # Redis keys
        self.presence_key = "verif:presence:active"
        self.session_key_template = "verif:session:{}"
        self.heartbeat_key_template = "verif:heartbeat:{}"
        self.stats_key = "verif:stats"
        
        # Channels
        self.task_notification_channel = "verif:tasks:new"
        self.task_assignment_channel = "verif:tasks:assigned"
        self.task_completion_channel = "verif:tasks:completed"
        self.system_broadcast_channel = "verif:system:broadcast"
        
        # Configuration
        self.heartbeat_timeout = int(os.getenv('HEARTBEAT_TIMEOUT', '60'))  # seconds
        self.cleanup_interval = int(os.getenv('CLEANUP_INTERVAL', '30'))  # seconds
        
        # State
        self.message_handlers = {}
        self.cleanup_task = None
        
    async def connect(self):
        """Initialize Redis connections"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            self.pubsub_client = redis.from_url(self.redis_url)
            
            await self.redis_client.ping()
            logger.info("✅ Connected to Redis for coordination")
            
            # Start cleanup task
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            return False

    async def disconnect(self):
        """Close Redis connections"""
        try:
            if self.cleanup_task:
                self.cleanup_task.cancel()
                
            if self.redis_client:
                await self.redis_client.close()
                
            if self.pubsub_client:
                await self.pubsub_client.close()
                
        except Exception as e:
            logger.error(f"❌ Error disconnecting from Redis: {e}")

    # ============================================================================
    # Presence Management
    # ============================================================================
    
    async def register_verifier_presence(
        self,
        session_id: str,
        user_id: str,
        user_name: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Register a verifier as present and active"""
        try:
            now = datetime.utcnow()
            presence_data = {
                'session_id': session_id,
                'user_id': user_id,
                'user_name': user_name,
                'connected_at': now.isoformat(),
                'last_heartbeat': now.isoformat(),
                'ip_address': ip_address,
                'user_agent': user_agent
            }
            
            # Add to active set
            await self.redis_client.sadd(self.presence_key, session_id)
            
            # Store session details
            session_key = self.session_key_template.format(session_id)
            await self.redis_client.hset(session_key, mapping=presence_data)
            await self.redis_client.expire(session_key, self.heartbeat_timeout * 2)
            
            # Set heartbeat
            heartbeat_key = self.heartbeat_key_template.format(session_id)
            await self.redis_client.setex(heartbeat_key, self.heartbeat_timeout, now.isoformat())
            
            logger.info(f"✅ Registered verifier presence: {user_name} (session: {session_id})")
            
            # Notify about new verifier
            await self.publish_system_broadcast({
                'type': 'verifier_connected',
                'session_id': session_id,
                'user_name': user_name,
                'timestamp': now.isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error registering verifier presence: {e}")
            return False

    async def update_verifier_heartbeat(self, session_id: str) -> bool:
        """Update verifier heartbeat"""
        try:
            now = datetime.utcnow()
            
            # Check if verifier is still in active set
            is_active = await self.redis_client.sismember(self.presence_key, session_id)
            if not is_active:
                return False
            
            # Update heartbeat
            heartbeat_key = self.heartbeat_key_template.format(session_id)
            await self.redis_client.setex(heartbeat_key, self.heartbeat_timeout, now.isoformat())
            
            # Update session last_heartbeat
            session_key = self.session_key_template.format(session_id)
            await self.redis_client.hset(session_key, 'last_heartbeat', now.isoformat())
            await self.redis_client.expire(session_key, self.heartbeat_timeout * 2)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating verifier heartbeat: {e}")
            return False

    async def remove_verifier_presence(self, session_id: str) -> bool:
        """Remove verifier from presence tracking"""
        try:
            # Get session info before removal
            session_key = self.session_key_template.format(session_id)
            session_data = await self.redis_client.hgetall(session_key)
            
            # Remove from active set
            await self.redis_client.srem(self.presence_key, session_id)
            
            # Clean up keys
            heartbeat_key = self.heartbeat_key_template.format(session_id)
            await self.redis_client.delete(session_key, heartbeat_key)
            
            # Notify about disconnection
            if session_data:
                user_name = session_data.get('user_name', 'Unknown')
                await self.publish_system_broadcast({
                    'type': 'verifier_disconnected',
                    'session_id': session_id,
                    'user_name': user_name,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
            logger.info(f"✅ Removed verifier presence: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error removing verifier presence: {e}")
            return False

    async def get_active_verifiers(self) -> List[VerifierPresence]:
        """Get all active verifiers"""
        try:
            session_ids = await self.redis_client.smembers(self.presence_key)
            verifiers = []
            
            for session_id in session_ids:
                session_key = self.session_key_template.format(session_id)
                session_data = await self.redis_client.hgetall(session_key)
                
                if session_data:
                    verifiers.append(VerifierPresence(
                        session_id=session_id,
                        user_id=session_data['user_id'],
                        user_name=session_data['user_name'],
                        connected_at=datetime.fromisoformat(session_data['connected_at']),
                        last_heartbeat=datetime.fromisoformat(session_data['last_heartbeat']),
                        ip_address=session_data.get('ip_address'),
                        user_agent=session_data.get('user_agent')
                    ))
            
            return verifiers
            
        except Exception as e:
            logger.error(f"❌ Error getting active verifiers: {e}")
            return []

    async def get_active_session_ids(self) -> List[str]:
        """Get list of active session IDs"""
        try:
            session_ids = await self.redis_client.smembers(self.presence_key)
            return list(session_ids)
        except Exception as e:
            logger.error(f"❌ Error getting active session IDs: {e}")
            return []

    async def is_verifier_active(self, session_id: str) -> bool:
        """Check if a verifier is currently active"""
        try:
            return await self.redis_client.sismember(self.presence_key, session_id)
        except Exception as e:
            logger.error(f"❌ Error checking verifier activity: {e}")
            return False

    # ============================================================================
    # Task Notifications
    # ============================================================================
    
    async def notify_new_task(self, task_data: Dict[str, Any]) -> bool:
        """Notify about a new verification task"""
        try:
            message = {
                'type': 'new_task',
                'data': task_data,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            await self.redis_client.publish(self.task_notification_channel, json.dumps(message))
            logger.debug(f"📢 Notified about new task: {task_data.get('id', 'unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error notifying new task: {e}")
            return False

    async def notify_task_assignment(self, task_id: str, session_id: str, user_name: str) -> bool:
        """Notify about task assignment"""
        try:
            message = {
                'type': 'task_assigned',
                'task_id': task_id,
                'session_id': session_id,
                'user_name': user_name,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            await self.redis_client.publish(self.task_assignment_channel, json.dumps(message))
            logger.debug(f"📢 Notified about task assignment: {task_id} to {user_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error notifying task assignment: {e}")
            return False

    async def notify_task_completion(self, task_id: str, session_id: str, action: str, user_name: str) -> bool:
        """Notify about task completion"""
        try:
            message = {
                'type': 'task_completed',
                'task_id': task_id,
                'session_id': session_id,
                'action': action,  # 'verified', 'rejected', 'released'
                'user_name': user_name,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            await self.redis_client.publish(self.task_completion_channel, json.dumps(message))
            logger.debug(f"📢 Notified about task completion: {task_id} ({action}) by {user_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error notifying task completion: {e}")
            return False

    async def publish_system_broadcast(self, message_data: Dict[str, Any]) -> bool:
        """Publish system-wide broadcast message"""
        try:
            message = {
                'timestamp': datetime.utcnow().isoformat(),
                **message_data
            }
            
            await self.redis_client.publish(self.system_broadcast_channel, json.dumps(message))
            return True
            
        except Exception as e:
            logger.error(f"❌ Error publishing system broadcast: {e}")
            return False

    # ============================================================================
    # Pub/Sub Management
    # ============================================================================
    
    async def subscribe_to_channel(self, channel: str, handler: Callable[[Dict[str, Any]], None]):
        """Subscribe to a Redis channel with message handler"""
        try:
            pubsub = self.pubsub_client.pubsub()
            await pubsub.subscribe(channel)
            
            self.message_handlers[channel] = handler
            
            logger.info(f"📡 Subscribed to channel: {channel}")
            
            # Start listening loop
            async def listen_loop():
                async for message in pubsub.listen():
                    if message['type'] == 'message':
                        try:
                            data = json.loads(message['data'])
                            await handler(data)
                        except Exception as e:
                            logger.error(f"❌ Error handling message from {channel}: {e}")
            
            asyncio.create_task(listen_loop())
            
        except Exception as e:
            logger.error(f"❌ Error subscribing to channel {channel}: {e}")

    # ============================================================================
    # Statistics
    # ============================================================================
    
    async def update_stats(self, stats: Dict[str, Any]) -> bool:
        """Update system statistics"""
        try:
            stats_data = {
                **stats,
                'last_updated': datetime.utcnow().isoformat()
            }
            
            await self.redis_client.hset(self.stats_key, mapping=stats_data)
            await self.redis_client.expire(self.stats_key, 3600)  # 1 hour TTL
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating stats: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get current system statistics"""
        try:
            stats = await self.redis_client.hgetall(self.stats_key)
            
            # Add real-time stats
            active_verifiers = len(await self.get_active_session_ids())
            stats['active_verifiers'] = str(active_verifiers)
            stats['last_checked'] = datetime.utcnow().isoformat()
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting stats: {e}")
            return {}

    # ============================================================================
    # Cleanup
    # ============================================================================
    
    async def cleanup_inactive_verifiers(self) -> int:
        """Clean up inactive verifiers based on heartbeat timeout"""
        try:
            session_ids = await self.redis_client.smembers(self.presence_key)
            inactive_count = 0
            
            for session_id in session_ids:
                heartbeat_key = self.heartbeat_key_template.format(session_id)
                heartbeat = await self.redis_client.get(heartbeat_key)
                
                if not heartbeat:
                    # No heartbeat found, remove verifier
                    await self.remove_verifier_presence(session_id)
                    inactive_count += 1
                    logger.info(f"🧹 Removed inactive verifier: {session_id}")
            
            return inactive_count
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up inactive verifiers: {e}")
            return 0

    async def _cleanup_loop(self):
        """Background cleanup task"""
        try:
            while True:
                await asyncio.sleep(self.cleanup_interval)
                
                # Clean up inactive verifiers
                inactive_count = await self.cleanup_inactive_verifiers()
                
                if inactive_count > 0:
                    logger.info(f"🧹 Cleanup cycle completed, removed {inactive_count} inactive verifiers")
                    
        except asyncio.CancelledError:
            logger.info("🛑 Cleanup loop cancelled")
        except Exception as e:
            logger.error(f"❌ Error in cleanup loop: {e}")

    # ============================================================================
    # Cache Management
    # ============================================================================
    
    async def cache_set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set a cached value with TTL"""
        try:
            serialized_value = json.dumps(value) if not isinstance(value, str) else value
            await self.redis_client.setex(f"verif:cache:{key}", ttl, serialized_value)
            return True
        except Exception as e:
            logger.error(f"❌ Error setting cache: {e}")
            return False

    async def cache_get(self, key: str) -> Optional[Any]:
        """Get a cached value"""
        try:
            value = await self.redis_client.get(f"verif:cache:{key}")
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            logger.error(f"❌ Error getting cache: {e}")
            return None

    async def cache_delete(self, key: str) -> bool:
        """Delete a cached value"""
        try:
            result = await self.redis_client.delete(f"verif:cache:{key}")
            return result > 0
        except Exception as e:
            logger.error(f"❌ Error deleting cache: {e}")
            return False