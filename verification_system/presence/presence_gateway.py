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
        \"\"\"Verify and decode JWT token\"\"\"
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
        \"\"\"Add verifier to active presence\"\"\"
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
        \"\"\"Remove verifier from active presence\"\"\"
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
    
    async def update_heartbeat(self, verifier_id: str):
        \"\"\"Update verifier heartbeat\"\"\"
        try:
            presence_key = self.presence_key_template.format(verifier_id)
            await asyncio.to_thread(
                self.redis_client.expire,
                presence_key,
                self.presence_ttl
            )
            
            # Update last seen
            capacity_key = self.capacity_key_template.format(verifier_id)
            await asyncio.to_thread(
                self.redis_client.hset,
                capacity_key,
                'last_seen',
                datetime.utcnow().isoformat()
            )
            
            self.stats['heartbeats'] += 1
            
        except Exception as e:
            logger.error(f"❌ Failed to update heartbeat for {verifier_id}: {e}")
    
    async def notify_rebalance_needed(self):
        \"\"\"Notify that rebalancing is needed\"\"\"
        try:
            # Publish rebalance signal
            await asyncio.to_thread(
                self.redis_client.publish,
                'verif:rebalance',
                json.dumps({
                    'timestamp': datetime.utcnow().isoformat(),
                    'trigger': 'verifier_disconnect'
                })
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to notify rebalance: {e}")
    
    async def listen_for_assignments(self, verifier_id: str, websocket: websockets.WebSocketServerProtocol):
        \"\"\"Listen for task assignments and forward to verifier\"\"\"
        assign_stream = self.assign_stream_template.format(verifier_id)
        
        try:
            # Use Redis Streams consumer to listen for assignments
            consumer_group = f"gateway:{verifier_id}"
            consumer_name = f"gateway:{verifier_id}:conn"
            
            # Create consumer group if it doesn't exist
            try:
                await asyncio.to_thread(
                    self.redis_client.xgroup_create,
                    assign_stream,
                    consumer_group,
                    id='0',
                    mkstream=True
                )
            except redis.RedisError:
                pass  # Group already exists
            
            while verifier_id in self.connections:
                try:
                    # Read new assignments
                    messages = await asyncio.to_thread(
                        self.redis_client.xreadgroup,
                        consumer_group,
                        consumer_name,
                        {assign_stream: '>'},
                        count=1,
                        block=1000  # 1 second timeout
                    )
                    
                    if messages:
                        for stream_name, stream_messages in messages:
                            for message_id, fields in stream_messages:
                                await self.forward_assignment(
                                    websocket,
                                    verifier_id,
                                    message_id,
                                    fields
                                )
                                
                except redis.TimeoutError:
                    continue  # Normal timeout, check if connection still active
                except Exception as e:
                    logger.error(f"❌ Error listening for assignments: {e}")
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error(f"❌ Failed to set up assignment listener: {e}")
    
    async def forward_assignment(self, websocket, verifier_id: str, message_id: str, fields: Dict[str, str]):
        \"\"\"Forward task assignment to verifier\"\"\"
        try:
            # Parse assignment data
            ann_id = fields.get('id')
            payload = json.loads(fields.get('payload', '{}'))
            assigned_ts = fields.get('ts')
            
            # Calculate deadline
            deadline_ms = int((datetime.utcnow() + timedelta(minutes=2)).timestamp() * 1000)
            
            # Prepare message for verifier
            assignment_msg = {
                'type': 'assign',
                'ann_id': ann_id,
                'payload': payload,
                'deadline_ms': deadline_ms,
                'assigned_at': assigned_ts,
                'message_id': message_id
            }
            
            # Send to verifier
            await websocket.send(json.dumps(assignment_msg))
            self.stats['messages_sent'] += 1
            
            logger.info(f"📤 Forwarded assignment {ann_id} to verifier {verifier_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to forward assignment: {e}")
    
    async def handle_message(self, websocket: websockets.WebSocketServerProtocol, message: str, verifier_id: str):
        \"\"\"Handle incoming message from verifier\"\"\"
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            self.stats['messages_received'] += 1
            
            if msg_type == 'heartbeat':
                await self.update_heartbeat(verifier_id)
                
            elif msg_type == 'ack':
                await self.handle_ack(verifier_id, data)
                
            elif msg_type == 'request_more':
                # Optional: trigger more assignment checks
                await self.notify_rebalance_needed()
                
            else:
                logger.warning(f"⚠️ Unknown message type: {msg_type}")
                
        except json.JSONDecodeError:
            logger.warning("⚠️ Invalid JSON from verifier")
        except Exception as e:
            logger.error(f"❌ Error handling message: {e}")
    
    async def handle_ack(self, verifier_id: str, ack_data: Dict[str, Any]):
        \"\"\"Handle acknowledgment from verifier\"\"\"
        try:
            ann_id = ack_data.get('ann_id')
            status = ack_data.get('status')
            note = ack_data.get('note', '')
            message_id = ack_data.get('message_id')
            
            if not ann_id or not status:
                logger.warning("⚠️ Invalid ACK data")
                return
            
            # Acknowledge the Redis Stream message
            if message_id:
                assign_stream = self.assign_stream_template.format(verifier_id)
                consumer_group = f"gateway:{verifier_id}"
                
                await asyncio.to_thread(
                    self.redis_client.xack,
                    assign_stream,
                    consumer_group,
                    message_id
                )
            
            # Store ACK result
            ack_key = f"verif:ack:{ann_id}"
            ack_value = f"{verifier_id}:{datetime.utcnow().isoformat()}:{status}"
            await asyncio.to_thread(
                self.redis_client.setex,
                ack_key,
                86400,  # 24 hours
                ack_value
            )
            
            # Remove from pending (this should be handled by dispatcher)
            pending_key = f"verif:pending:{verifier_id}"
            await asyncio.to_thread(
                self.redis_client.zrem,
                pending_key,
                ann_id
            )
            
            # Update capacity
            capacity_key = self.capacity_key_template.format(verifier_id)
            await asyncio.to_thread(
                self.redis_client.hincrby,
                capacity_key,
                'inflight',
                -1
            )
            
            self.stats['acks'] += 1
            logger.info(f"✅ ACK {status} for {ann_id} from {verifier_id}")
            
            # TODO: Store to Supabase verification_events table
            
        except Exception as e:
            logger.error(f"❌ Error handling ACK: {e}")
    
    async def handle_verifier_connection(self, websocket: websockets.WebSocketServerProtocol, path: str):
        \"\"\"Handle new verifier WebSocket connection\"\"\"
        verifier_id = None
        
        try:
            # Get JWT token from query parameters or headers
            token = None
            
            # Try query parameter first: ws://host/verifier?token=...
            if '?' in path:
                query_params = dict(param.split('=', 1) for param in path.split('?', 1)[1].split('&') if '=' in param)
                token = query_params.get('token')
            
            # Try Sec-WebSocket-Protocol header as fallback
            if not token:
                token = websocket.request_headers.get('Sec-WebSocket-Protocol')
            
            if not token:
                await websocket.close(code=4000, reason="Missing authentication token")
                return
            
            # Verify JWT token
            payload = self.verify_jwt_token(token)
            if not payload:
                await websocket.close(code=4001, reason="Invalid authentication token")
                return
            
            verifier_id = payload['verifier_id']
            
            # Check if too many verifiers are active
            active_count = await asyncio.to_thread(self.redis_client.scard, self.active_verifiers_key)
            if active_count >= self.max_verifiers:
                await websocket.close(code=4002, reason="Maximum verifiers limit reached")
                return
            
            # Add to presence
            await self.add_verifier_to_presence(verifier_id)
            
            # Store connection
            self.connections[verifier_id] = websocket
            self.verifier_ids[websocket] = verifier_id
            self.stats['connections_total'] += 1
            self.stats['connections_active'] += 1
            
            logger.info(f"👋 Verifier {verifier_id} connected")
            
            # Send welcome message
            welcome_msg = {
                'type': 'info',
                'message': f'Connected as verifier {verifier_id}',
                'heartbeat_interval': self.heartbeat_interval
            }
            await websocket.send(json.dumps(welcome_msg))
            
            # Start assignment listener
            assignment_task = asyncio.create_task(
                self.listen_for_assignments(verifier_id, websocket)
            )
            
            # Message handling loop
            async for message in websocket:
                await self.handle_message(websocket, message, verifier_id)
                
        except ConnectionClosed:
            logger.info(f"👋 Verifier {verifier_id} disconnected")
        except WebSocketException as e:
            logger.warning(f"⚠️ WebSocket error for {verifier_id}: {e}")
        except Exception as e:
            logger.error(f"❌ Error handling verifier connection: {e}")
        finally:
            # Cleanup
            if verifier_id:
                await self.remove_verifier_from_presence(verifier_id)
                
                if verifier_id in self.connections:
                    del self.connections[verifier_id]
                    
                if websocket in self.verifier_ids:
                    del self.verifier_ids[websocket]
                    
                self.stats['connections_active'] -= 1
    
    async def start_server(self):
        \"\"\"Start the WebSocket server\"\"\"
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
    
    async def get_stats(self):
        \"\"\"Get current gateway statistics\"\"\"
        try:
            active_verifiers = await asyncio.to_thread(
                self.redis_client.smembers,
                self.active_verifiers_key
            )
            
            return {
                **self.stats,
                'active_verifiers': len(active_verifiers),
                'verifier_ids': list(active_verifiers),
                'max_verifiers': self.max_verifiers
            }
        except Exception:
            return self.stats

async def main():
    \"\"\"Main entry point\"\"\"
    gateway = PresenceGateway()
    await gateway.start_server()

if __name__ == "__main__":
    asyncio.run(main())