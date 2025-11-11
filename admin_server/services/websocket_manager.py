import asyncio
import json
import logging
from typing import List, Set, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

from services.supabase_client import supabase_service
from services.task_manager import TaskManager

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self, task_manager: TaskManager):
        self.active_connections: List[WebSocket] = []
        self.task_manager = task_manager
        self.stats_broadcast_interval = 5  # Broadcast stats every 5 seconds
        self.is_running = False
        
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"✅ WebSocket connected. Total connections: {len(self.active_connections)}")
        
        # Send initial stats to the new connection
        await self.send_stats_to_connection(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"❌ WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"❌ Failed to send personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected WebSockets"""
        if not self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"❌ Failed to broadcast to connection: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)
    
    async def get_current_stats(self) -> Dict[str, Any]:
        """Get current system statistics"""
        try:
            # Get queue stats from Supabase
            queue_stats = await supabase_service.get_queue_stats()
            
            # Get Redis stream info
            stream_info = await self.task_manager.get_stream_info()
            consumer_info = await self.task_manager.get_consumer_info()
            
            # Count online users (active consumers)
            online_users = []
            for consumer in consumer_info:
                if consumer["idle_time"] < 60000:  # Active in last minute
                    # Extract user info from consumer name (user:{userId}:session:{sessionId})
                    consumer_parts = consumer["name"].split(":")
                    if len(consumer_parts) >= 2 and consumer_parts[0] == "user":
                        online_users.append(consumer_parts[1])
            
            # Remove duplicates (same user, multiple sessions)
            unique_users = list(set(online_users))
            
            return {
                "type": "queue_stats",
                "data": {
                    **queue_stats,
                    "my_assigned_count": 0,  # Will be overridden per user
                    "stream_length": stream_info.get("stream_length", 0),
                    "online_users": len(unique_users),
                    "online_user_list": unique_users,
                    "active_consumers": len([c for c in consumer_info if c["idle_time"] < 60000]),
                    "total_consumers": len(consumer_info),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        except Exception as e:
            logger.error(f"❌ Failed to get current stats: {e}")
            return {
                "type": "error",
                "data": {
                    "message": "Failed to get system stats",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
    
    async def send_stats_to_connection(self, websocket: WebSocket):
        """Send current stats to a specific connection"""
        stats = await self.get_current_stats()
        await self.send_personal_message(stats, websocket)
    
    async def broadcast_stats(self):
        """Broadcast current stats to all connections"""
        stats = await self.get_current_stats()
        await self.broadcast(stats)
    
    async def broadcast_stats_loop(self):
        """Background task to broadcast stats periodically"""
        self.is_running = True
        logger.info(f"🔄 Started stats broadcast loop (every {self.stats_broadcast_interval}s)")
        
        while self.is_running:
            try:
                if self.active_connections:
                    await self.broadcast_stats()
                await asyncio.sleep(self.stats_broadcast_interval)
            except Exception as e:
                logger.error(f"❌ Error in stats broadcast loop: {e}")
                await asyncio.sleep(self.stats_broadcast_interval)
    
    async def stop_broadcast_loop(self):
        """Stop the stats broadcast loop"""
        self.is_running = False
        logger.info("🛑 Stopped stats broadcast loop")
    
    async def notify_task_assigned(self, user_id: str, task_id: str):
        """Send notification when a task is assigned to a user"""
        message = {
            "type": "task_assigned",
            "data": {
                "task_id": task_id,
                "user_id": user_id,
                "message": f"New task {task_id[:8]}... assigned to you",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        # For now, broadcast to all (in a real app, you'd send to specific user)
        await self.broadcast(message)
    
    async def notify_task_completed(self, user_id: str, task_id: str, verified: bool):
        """Send notification when a task is completed"""
        message = {
            "type": "task_completed",
            "data": {
                "task_id": task_id,
                "user_id": user_id,
                "verified": verified,
                "message": f"Task {task_id[:8]}... {'verified' if verified else 'rejected'}",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        await self.broadcast(message)
    
    async def notify_user_activity(self, user_id: str, action: str, details: Dict[str, Any] = None):
        """Send notification about user activity"""
        message = {
            "type": "user_activity",
            "data": {
                "user_id": user_id,
                "action": action,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        await self.broadcast(message)
    
    async def send_system_message(self, message_text: str, message_type: str = "info"):
        """Send a system message to all connected users"""
        message = {
            "type": "system_message",
            "data": {
                "message": message_text,
                "message_type": message_type,  # info, warning, error, success
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        await self.broadcast(message)
    
    def get_connection_count(self) -> int:
        """Get the number of active WebSocket connections"""
        return len(self.active_connections)
    
    async def ping_all_connections(self):
        """Send a ping to all connections to check if they're alive"""
        if not self.active_connections:
            return
        
        ping_message = {
            "type": "ping",
            "data": {
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        await self.broadcast(ping_message)