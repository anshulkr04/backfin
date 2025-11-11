#!/usr/bin/env python3
"""
Dispatcher - Round-robin assignment with visibility timeout

Implements fair distribution of verification tasks among active verifiers.
Handles visibility timeout, reassignment, and equal distribution.
"""

import os
import redis
import json
import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Set, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('dispatcher')

class VerificationDispatcher:
    def __init__(self):
        # Redis connection
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = None
        
        # Redis keys
        self.backlog_stream = 'verif:backlog'
        self.active_verifiers_key = 'verifiers:active'
        self.last_index_key = 'verif:last_index'
        self.assign_stream_template = 'verif:assign:{}'
        self.pending_key_template = 'verif:pending:{}'
        self.rebalance_channel = 'verif:rebalance'
        
        # Configuration
        self.enabled = os.getenv('VERIFICATION_ENABLED', 'true').lower() == 'true'
        self.batch_size = int(os.getenv('DISPATCH_BATCH_SIZE', '10'))
        self.dispatch_interval = int(os.getenv('DISPATCH_INTERVAL', '2'))  # seconds
        self.visibility_timeout = int(os.getenv('VISIBILITY_TIMEOUT', '120'))  # seconds
        self.timeout_check_interval = int(os.getenv('TIMEOUT_CHECK_INTERVAL', '30'))  # seconds
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        
        # State
        self.shutdown = False
        self.last_dispatch = datetime.min
        self.last_timeout_check = datetime.min
        
        # Stats
        self.stats = {
            'dispatches_total': 0,
            'assignments_total': 0,
            'timeouts_total': 0,
            'reassignments_total': 0,
            'deadletters_total': 0,
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
    
    async def get_active_verifiers(self) -> List[str]:
        """Get sorted list of active verifiers"""
        try:
            active_set = await asyncio.to_thread(
                self.redis_client.smembers,
                self.active_verifiers_key
            )
            
            # Convert to sorted list for deterministic round-robin
            active_list = sorted(list(active_set))
            return active_list
            
        except Exception as e:
            logger.error(f"❌ Error getting active verifiers: {e}")
            return []
    
    async def get_backlog_items(self, count: int = None) -> List[Dict[str, Any]]:
        """Get items from verification backlog"""
        try:
            count = count or self.batch_size
            
            # Get messages from stream
            messages = await asyncio.to_thread(
                self.redis_client.xrange,
                self.backlog_stream,
                '-', '+',
                count=count
            )
            
            backlog_items = []
            for message_id, fields in messages:
                backlog_items.append({
                    'stream_id': message_id,
                    'ann_id': fields.get('id'),
                    'payload': fields.get('payload', '{}'),
                    'ts': fields.get('ts'),
                    'source': fields.get('source', 'unknown')
                })
            
            return backlog_items
            
        except Exception as e:
            logger.error(f"❌ Error getting backlog items: {e}")
            return []
    
    async def get_last_index(self) -> int:
        """Get the last round-robin index"""
        try:
            last_index = await asyncio.to_thread(
                self.redis_client.get,
                self.last_index_key
            )
            return int(last_index) if last_index else 0
        except Exception as e:
            logger.warning(f"⚠️ Error getting last index: {e}")
            return 0
    
    async def set_last_index(self, index: int):
        """Set the last round-robin index"""
        try:
            await asyncio.to_thread(
                self.redis_client.set,
                self.last_index_key,
                str(index)
            )
        except Exception as e:
            logger.warning(f"⚠️ Error setting last index: {e}")
    
    async def assign_to_verifier(self, verifier_id: str, backlog_item: Dict[str, Any]) -> bool:
        """Assign a task to a specific verifier"""
        try:
            ann_id = backlog_item['ann_id']
            assign_stream = self.assign_stream_template.format(verifier_id)
            pending_key = self.pending_key_template.format(verifier_id)
            
            # Check for duplicate assignment (safety check)
            inflight_key = f"verif:inflight:{ann_id}"
            if await asyncio.to_thread(self.redis_client.exists, inflight_key):
                logger.warning(f"⚠️ Task {ann_id} already in flight, skipping")
                return False
            
            # Set inflight lock
            await asyncio.to_thread(
                self.redis_client.setex,
                inflight_key,
                self.visibility_timeout,
                verifier_id
            )
            
            # Add to verifier's assignment stream
            assignment_data = {
                'id': ann_id,
                'payload': backlog_item['payload'],
                'ts': backlog_item['ts'],
                'assigned_at': datetime.utcnow().isoformat(),
                'source_stream_id': backlog_item['stream_id']
            }
            
            await asyncio.to_thread(
                self.redis_client.xadd,
                assign_stream,
                assignment_data
            )
            
            # Add to pending set with score = assignment timestamp
            now_ms = int(datetime.utcnow().timestamp() * 1000)
            await asyncio.to_thread(
                self.redis_client.zadd,
                pending_key,
                {ann_id: now_ms}
            )
            
            # Remove from backlog (strict move semantics)
            await asyncio.to_thread(
                self.redis_client.xdel,
                self.backlog_stream,
                backlog_item['stream_id']
            )
            
            logger.info(f"📋 Assigned {ann_id} to verifier {verifier_id}")
            self.stats['assignments_total'] += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Error assigning to verifier {verifier_id}: {e}")
            return False
    
    async def dispatch_round_robin(self, active_verifiers: List[str], backlog_items: List[Dict[str, Any]]):
        """Dispatch items using round-robin algorithm"""
        if not active_verifiers or not backlog_items:
            return 0
        
        try:
            last_index = await self.get_last_index()
            assigned_count = 0
            
            for i, item in enumerate(backlog_items):
                # Calculate round-robin target
                target_index = (last_index + i) % len(active_verifiers)
                target_verifier = active_verifiers[target_index]
                
                # Assign to target verifier
                if await self.assign_to_verifier(target_verifier, item):
                    assigned_count += 1
                else:
                    # If assignment failed, don't count it in the index increment
                    continue
            
            # Update last index for next round
            if assigned_count > 0:
                new_index = (last_index + assigned_count) % len(active_verifiers)
                await self.set_last_index(new_index)
            
            self.stats['dispatches_total'] += 1
            return assigned_count
            
        except Exception as e:
            logger.error(f"❌ Error in round-robin dispatch: {e}")
            return 0
    
    async def check_visibility_timeouts(self, active_verifiers: List[str]):
        """Check for timed-out assignments and reassign"""
        try:
            timeout_ms = int((datetime.utcnow() - timedelta(seconds=self.visibility_timeout)).timestamp() * 1000)
            timed_out_items = []
            
            for verifier_id in active_verifiers:
                pending_key = self.pending_key_template.format(verifier_id)
                
                # Get timed-out items
                timed_out = await asyncio.to_thread(
                    self.redis_client.zrangebyscore,
                    pending_key,
                    '-inf',
                    timeout_ms,
                    withscores=True
                )
                
                for ann_id, score in timed_out:
                    # Remove from pending
                    await asyncio.to_thread(
                        self.redis_client.zrem,
                        pending_key,
                        ann_id
                    )
                    
                    # Clear inflight lock
                    inflight_key = f"verif:inflight:{ann_id}"
                    await asyncio.to_thread(
                        self.redis_client.delete,
                        inflight_key
                    )
                    
                    # Check retry count
                    retry_key = f"verif:retries:{ann_id}"
                    retry_count = await asyncio.to_thread(
                        self.redis_client.incr,
                        retry_key
                    )
                    
                    if retry_count > self.max_retries:
                        # Move to dead letter queue
                        await self.move_to_deadletter(ann_id, verifier_id, "max_retries_exceeded")
                        self.stats['deadletters_total'] += 1
                        logger.warning(f"💀 Moved {ann_id} to dead letter (max retries)")
                    else:
                        # Re-queue for assignment
                        await self.requeue_announcement(ann_id, verifier_id, retry_count)
                        self.stats['reassignments_total'] += 1
                        logger.info(f"🔄 Requeued {ann_id} (timeout from {verifier_id}, retry {retry_count})")
                    
                    self.stats['timeouts_total'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error checking visibility timeouts: {e}")
    
    async def requeue_announcement(self, ann_id: str, failed_verifier: str, retry_count: int):
        """Requeue an announcement back to the backlog"""
        try:
            # Create backlog entry (we need to reconstruct the payload)
            # This is a limitation - we should store original data somewhere
            # For now, create a minimal entry
            requeue_data = {
                'id': ann_id,
                'payload': json.dumps({
                    'ann_id': ann_id,
                    'retry_count': retry_count,
                    'failed_verifier': failed_verifier,
                    'requeued_at': datetime.utcnow().isoformat()
                }),
                'ts': datetime.utcnow().isoformat(),
                'source': 'requeue'
            }
            
            await asyncio.to_thread(
                self.redis_client.xadd,
                self.backlog_stream,
                requeue_data
            )
            
        except Exception as e:
            logger.error(f"❌ Error requeuing {ann_id}: {e}")
    
    async def move_to_deadletter(self, ann_id: str, failed_verifier: str, reason: str):
        """Move announcement to dead letter queue"""
        try:
            deadletter_data = {
                'ann_id': ann_id,
                'failed_verifier': failed_verifier,
                'reason': reason,
                'deadlettered_at': datetime.utcnow().isoformat()
            }
            
            await asyncio.to_thread(
                self.redis_client.xadd,
                'verif:deadletter',
                deadletter_data
            )
            
        except Exception as e:
            logger.error(f"❌ Error moving {ann_id} to deadletter: {e}")
    
    async def listen_for_rebalance_signals(self):
        """Listen for rebalance signals from presence gateway"""
        try:
            pubsub = self.redis_client.pubsub()
            await asyncio.to_thread(pubsub.subscribe, self.rebalance_channel)
            
            logger.info(f"👂 Listening for rebalance signals on {self.rebalance_channel}")
            
            while not self.shutdown:
                try:
                    message = await asyncio.to_thread(pubsub.get_message, timeout=1.0)
                    if message and message['type'] == 'message':
                        logger.info("🔄 Received rebalance signal, triggering dispatch")
                        await self.dispatch_once()
                        
                except redis.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"❌ Error in rebalance listener: {e}")
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error(f"❌ Failed to set up rebalance listener: {e}")
    
    async def dispatch_once(self):
        """Perform one dispatch cycle"""
        if not self.enabled:
            return
        
        try:
            # Get active verifiers
            active_verifiers = await self.get_active_verifiers()
            
            if not active_verifiers:
                logger.debug("⏸️ No active verifiers, skipping dispatch")
                return
            
            # Get backlog items
            backlog_items = await self.get_backlog_items()
            
            if not backlog_items:
                logger.debug("📭 No items in backlog")
                return
            
            # Dispatch using round-robin
            assigned_count = await self.dispatch_round_robin(active_verifiers, backlog_items)
            
            if assigned_count > 0:
                logger.info(f"📤 Dispatched {assigned_count} items to {len(active_verifiers)} verifiers")
            
            self.last_dispatch = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"❌ Error in dispatch cycle: {e}")
    
    async def timeout_check_cycle(self):
        """Perform timeout check cycle"""
        try:
            active_verifiers = await self.get_active_verifiers()
            if active_verifiers:
                await self.check_visibility_timeouts(active_verifiers)
            
            self.last_timeout_check = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"❌ Error in timeout check: {e}")
    
    async def run(self):
        """Main execution loop"""
        logger.info(f"🚀 Starting Verification Dispatcher")
        logger.info(f"   Enabled: {self.enabled}")
        logger.info(f"   Batch Size: {self.batch_size}")
        logger.info(f"   Dispatch Interval: {self.dispatch_interval}s")
        logger.info(f"   Visibility Timeout: {self.visibility_timeout}s")
        
        # Connect to Redis
        if not await self.connect_redis():
            return False
        
        # Start rebalance listener in background
        rebalance_task = asyncio.create_task(self.listen_for_rebalance_signals())
        
        try:
            while not self.shutdown:
                now = datetime.utcnow()
                
                # Dispatch cycle
                if (now - self.last_dispatch).total_seconds() >= self.dispatch_interval:
                    await self.dispatch_once()
                
                # Timeout check cycle
                if (now - self.last_timeout_check).total_seconds() >= self.timeout_check_interval:
                    await self.timeout_check_cycle()
                
                # Brief pause
                await asyncio.sleep(1)
                
        finally:
            rebalance_task.cancel()
            try:
                await rebalance_task
            except asyncio.CancelledError:
                pass
        
        logger.info("⏹️ Verification Dispatcher stopped")
        return True
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signal"""
        logger.info(f"📨 Received signal {signum}, shutting down...")
        self.shutdown = True
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        try:
            backlog_length = await asyncio.to_thread(
                self.redis_client.xlen,
                self.backlog_stream
            )
            
            active_verifiers = await self.get_active_verifiers()
            
            return {
                **self.stats,
                'backlog_length': backlog_length,
                'active_verifiers': len(active_verifiers),
                'enabled': self.enabled,
                'last_dispatch': self.last_dispatch.isoformat(),
                'last_timeout_check': self.last_timeout_check.isoformat()
            }
        except Exception:
            return self.stats

async def main():
    """Main entry point"""
    dispatcher = VerificationDispatcher()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, dispatcher.handle_shutdown)
    signal.signal(signal.SIGTERM, dispatcher.handle_shutdown)
    
    # Run dispatcher
    success = await dispatcher.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())