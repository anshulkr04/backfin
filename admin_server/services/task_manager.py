import os
import redis.asyncio as redis
import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.stream_name = "admin:verification:stream"
        self.consumer_group = "admin:verification:workers"
        self.redis_client = None
        
    async def initialize(self):
        """Initialize Redis connection and consumer group"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            
            # Test connection
            await self.redis_client.ping()
            logger.info("✅ Connected to Redis")
            
            # Create consumer group if it doesn't exist
            try:
                await self.redis_client.xgroup_create(
                    self.stream_name, 
                    self.consumer_group, 
                    id='0', 
                    mkstream=True
                )
                logger.info(f"✅ Created consumer group: {self.consumer_group}")
            except redis.RedisError as e:
                if "BUSYGROUP" in str(e):
                    logger.info(f"✅ Consumer group already exists: {self.consumer_group}")
                else:
                    raise e
                    
        except Exception as e:
            logger.error(f"❌ Failed to initialize Redis: {e}")
            raise e
    
    async def cleanup(self):
        """Cleanup Redis connections"""
        if self.redis_client:
            await self.redis_client.close()
    
    async def add_task_to_stream(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """Add a verification task to the Redis stream"""
        try:
            # Prepare stream data
            stream_data = {
                "task_id": task_id,
                "task_data": json.dumps(task_data),
                "created_at": datetime.utcnow().isoformat(),
                "status": "queued"
            }
            
            # Add to stream
            message_id = await self.redis_client.xadd(self.stream_name, stream_data)
            logger.info(f"✅ Added task {task_id} to stream with message ID: {message_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add task to stream: {e}")
            return False
    
    async def claim_next_task(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Claim the next available task for a user"""
        try:
            consumer_name = f"user:{user_id}:session:{session_id}"
            
            # Read from stream with consumer group
            messages = await self.redis_client.xreadgroup(
                self.consumer_group,
                consumer_name,
                {self.stream_name: '>'},
                count=1,
                block=100  # Block for 100ms
            )
            
            if messages:
                stream_name, stream_messages = messages[0]
                if stream_messages:
                    message_id, fields = stream_messages[0]
                    
                    # Decode the task data
                    task_data = {
                        "message_id": message_id.decode() if isinstance(message_id, bytes) else message_id,
                        "task_id": fields[b'task_id'].decode() if b'task_id' in fields else None,
                        "task_data": json.loads(fields[b'task_data'].decode()) if b'task_data' in fields else {},
                        "created_at": fields[b'created_at'].decode() if b'created_at' in fields else None,
                        "claimed_by": consumer_name,
                        "claimed_at": datetime.utcnow().isoformat()
                    }
                    
                    logger.info(f"✅ Task {task_data['task_id']} claimed by {consumer_name}")
                    return task_data
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to claim task: {e}")
            return None
    
    async def acknowledge_task(self, message_id: str) -> bool:
        """Acknowledge that a task has been completed"""
        try:
            result = await self.redis_client.xack(self.stream_name, self.consumer_group, message_id)
            logger.info(f"✅ Acknowledged task with message ID: {message_id}")
            return result > 0
        except Exception as e:
            logger.error(f"❌ Failed to acknowledge task: {e}")
            return False
    
    async def get_pending_tasks(self, consumer_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pending tasks from the stream"""
        try:
            # Get pending messages
            pending_info = await self.redis_client.xpending(self.stream_name, self.consumer_group)
            
            if pending_info[0] == 0:  # No pending messages
                return []
            
            # Get detailed pending info
            pending_details = await self.redis_client.xpending_range(
                self.stream_name,
                self.consumer_group,
                min='-',
                max='+',
                count=100
            )
            
            pending_tasks = []
            for detail in pending_details:
                message_id, consumer, idle_time, delivery_count = detail
                
                # Filter by consumer if specified
                if consumer_name and consumer.decode() != consumer_name:
                    continue
                
                pending_tasks.append({
                    "message_id": message_id.decode(),
                    "consumer": consumer.decode(),
                    "idle_time_ms": idle_time,
                    "delivery_count": delivery_count
                })
            
            return pending_tasks
            
        except Exception as e:
            logger.error(f"❌ Failed to get pending tasks: {e}")
            return []
    
    async def reclaim_stale_tasks(self, idle_time_ms: int = 600000) -> int:
        """Reclaim tasks that have been idle for too long (default 10 minutes)"""
        try:
            # Get pending tasks
            pending_details = await self.redis_client.xpending_range(
                self.stream_name,
                self.consumer_group,
                min='-',
                max='+',
                count=100
            )
            
            reclaimed_count = 0
            claimer_consumer = "system:reclaimer"
            
            for detail in pending_details:
                message_id, consumer, idle_time, delivery_count = detail
                
                # Reclaim if idle too long
                if idle_time >= idle_time_ms:
                    try:
                        result = await self.redis_client.xclaim(
                            self.stream_name,
                            self.consumer_group,
                            claimer_consumer,
                            idle_time_ms,
                            message_id
                        )
                        
                        if result:
                            reclaimed_count += 1
                            logger.info(f"🔄 Reclaimed stale task {message_id.decode()} from {consumer.decode()}")
                    except Exception as e:
                        logger.error(f"❌ Failed to reclaim task {message_id.decode()}: {e}")
            
            if reclaimed_count > 0:
                logger.info(f"🔄 Reclaimed {reclaimed_count} stale tasks")
            
            return reclaimed_count
            
        except Exception as e:
            logger.error(f"❌ Failed to reclaim stale tasks: {e}")
            return 0
    
    async def get_stream_info(self) -> Dict[str, Any]:
        """Get information about the verification stream"""
        try:
            stream_info = await self.redis_client.xinfo_stream(self.stream_name)
            group_info = await self.redis_client.xinfo_groups(self.stream_name)
            
            return {
                "stream_length": stream_info[b'length'],
                "total_entries": stream_info[b'entries-added'],
                "consumer_groups": len(group_info),
                "last_entry_id": stream_info[b'last-entry'][0].decode() if stream_info[b'last-entry'] else None
            }
        except Exception as e:
            logger.error(f"❌ Failed to get stream info: {e}")
            return {}
    
    async def get_consumer_info(self) -> List[Dict[str, Any]]:
        """Get information about consumers in the group"""
        try:
            consumers = await self.redis_client.xinfo_consumers(self.stream_name, self.consumer_group)
            
            consumer_list = []
            for consumer in consumers:
                consumer_list.append({
                    "name": consumer[b'name'].decode(),
                    "pending_count": consumer[b'pending'],
                    "idle_time": consumer[b'idle'],
                })
            
            return consumer_list
        except Exception as e:
            logger.error(f"❌ Failed to get consumer info: {e}")
            return []
    
    async def release_user_tasks(self, user_id: str, session_id: str) -> int:
        """Release all tasks assigned to a specific user session"""
        try:
            consumer_name = f"user:{user_id}:session:{session_id}"
            
            # Get pending tasks for this consumer
            pending_tasks = await self.get_pending_tasks(consumer_name)
            
            released_count = 0
            for task in pending_tasks:
                # Move task back to the stream by claiming it with a system consumer
                # then immediately acknowledging it (this removes it from pending)
                try:
                    await self.redis_client.xclaim(
                        self.stream_name,
                        self.consumer_group,
                        "system:releaser",
                        0,  # Min idle time 0 to force claim
                        task["message_id"]
                    )
                    
                    # Acknowledge to remove from pending
                    await self.redis_client.xack(self.stream_name, self.consumer_group, task["message_id"])
                    released_count += 1
                    
                except Exception as e:
                    logger.error(f"❌ Failed to release task {task['message_id']}: {e}")
            
            if released_count > 0:
                logger.info(f"🔄 Released {released_count} tasks for user {user_id}")
            
            return released_count
            
        except Exception as e:
            logger.error(f"❌ Failed to release user tasks: {e}")
            return 0