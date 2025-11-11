#!/usr/bin/env python3
"""
Announcement Tap - Mirrors announcements to verification backlog

This service subscribes to the existing announcement pipeline and mirrors
every announcement to the verification backlog without affecting the main flow.

Features:
- Non-intrusive: Only reads from existing pub/sub
- Safe: No changes to existing queues or processing
- Observable: Metrics and logging for monitoring
"""

import os
import redis
import json
import logging
import asyncio
import signal
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('announcement-tap')

class AnnouncementTap:
    def __init__(self):
        # Redis connections
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.pubsub_client = None
        self.stream_client = None
        
        # Configuration
        self.source_channel = os.getenv('SOURCE_CHANNEL', 'announcements:new')
        self.backlog_stream = os.getenv('BACKLOG_STREAM', 'verif:backlog')
        self.enabled = os.getenv('VERIFICATION_TAP_ENABLED', 'true').lower() == 'true'
        
        # Metrics
        self.stats = {
            'messages_received': 0,
            'messages_mirrored': 0,
            'errors': 0,
            'started_at': datetime.utcnow().isoformat()
        }
        
        # Shutdown flag
        self.shutdown = False
        
    async def connect(self):
        """Initialize Redis connections"""
        try:
            # Pub/Sub client for listening to announcements
            self.pubsub_client = redis.from_url(self.redis_url)
            
            # Stream client for writing to backlog
            self.stream_client = redis.from_url(self.redis_url)
            
            # Test connections
            await asyncio.to_thread(self.pubsub_client.ping)
            await asyncio.to_thread(self.stream_client.ping)
            
            logger.info("✅ Connected to Redis")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            return False
    
    async def subscribe_to_announcements(self):
        """Subscribe to announcement channel"""
        try:
            pubsub = self.pubsub_client.pubsub()
            await asyncio.to_thread(pubsub.subscribe, self.source_channel)
            logger.info(f"📡 Subscribed to {self.source_channel}")
            return pubsub
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe: {e}")
            return None
    
    async def mirror_to_backlog(self, announcement_data: Dict[str, Any]) -> bool:
        """Mirror announcement to verification backlog"""
        if not self.enabled:
            logger.debug("🔇 Verification tap disabled, skipping")
            return False
            
        try:
            # Extract announcement ID (use corp_id or generate one)
            ann_id = announcement_data.get('corp_id') or announcement_data.get('id') or f"ann_{int(datetime.utcnow().timestamp() * 1000)}"
            
            # Prepare stream entry
            stream_data = {
                'id': ann_id,
                'payload': json.dumps(announcement_data),
                'ts': datetime.utcnow().isoformat(),
                'source': 'tap'
            }
            
            # Add to verification backlog stream
            stream_id = await asyncio.to_thread(
                self.stream_client.xadd,
                self.backlog_stream,
                stream_data
            )
            
            self.stats['messages_mirrored'] += 1
            logger.info(f"🪞 Mirrored announcement {ann_id} → {stream_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to mirror announcement: {e}")
            self.stats['errors'] += 1
            return False
    
    async def process_message(self, message):
        """Process a single announcement message"""
        try:
            if message['type'] != 'message':
                return
                
            self.stats['messages_received'] += 1
            
            # Parse message data
            raw_data = message['data']
            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode('utf-8')
            
            announcement_data = json.loads(raw_data)
            
            # Mirror to verification backlog
            await self.mirror_to_backlog(announcement_data)
            
            # Log every 10 messages
            if self.stats['messages_received'] % 10 == 0:
                logger.info(f"📊 Stats: {self.stats['messages_received']} received, {self.stats['messages_mirrored']} mirrored")
                
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Invalid JSON in message: {e}")
            self.stats['errors'] += 1
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
            self.stats['errors'] += 1
    
    async def run(self):
        \"\"\"Main execution loop\"\"\"
        logger.info(f"🚀 Starting Announcement Tap")
        logger.info(f"   Source Channel: {self.source_channel}")
        logger.info(f"   Backlog Stream: {self.backlog_stream}")
        logger.info(f"   Enabled: {self.enabled}")
        
        # Connect to Redis
        if not await self.connect():
            return False
        
        # Subscribe to announcements
        pubsub = await self.subscribe_to_announcements()
        if not pubsub:
            return False
        
        try:
            # Main message processing loop
            while not self.shutdown:
                try:
                    # Get message with timeout
                    message = await asyncio.to_thread(pubsub.get_message, timeout=1.0)
                    
                    if message:
                        await self.process_message(message)
                    
                    # Brief pause to prevent tight loop
                    await asyncio.sleep(0.01)
                    
                except redis.ConnectionError:
                    logger.warning("📡 Redis connection lost, attempting to reconnect...")
                    await asyncio.sleep(5)
                    if not await self.connect():
                        logger.error("❌ Failed to reconnect to Redis")
                        break
                        
                except Exception as e:
                    logger.error(f"❌ Error in main loop: {e}")
                    await asyncio.sleep(1)
                    
        finally:
            # Cleanup
            try:
                await asyncio.to_thread(pubsub.close)
                self.pubsub_client.close()
                self.stream_client.close()
                logger.info("🧹 Cleanup completed")
            except Exception as e:
                logger.warning(f"⚠️ Cleanup error: {e}")
        
        logger.info("⏹️ Announcement Tap stopped")
        return True
    
    def handle_shutdown(self, signum, frame):
        \"\"\"Handle shutdown signal\"\"\"
        logger.info(f"📨 Received signal {signum}, shutting down...")
        self.shutdown = True
    
    async def get_stats(self) -> Dict[str, Any]:
        \"\"\"Get current statistics\"\"\"
        return {
            **self.stats,
            'uptime_seconds': (datetime.utcnow() - datetime.fromisoformat(self.stats['started_at'])).total_seconds(),
            'enabled': self.enabled,
            'source_channel': self.source_channel,
            'backlog_stream': self.backlog_stream
        }

# Test harness for local development
async def test_publisher():
    \"\"\"Test publisher that simulates announcements\"\"\"
    redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
    
    test_announcements = [
        {
            "corp_id": "TEST001",
            "title": "Test Announcement 1",
            "companyname": "Test Company Ltd",
            "category": "Board Meeting",
            "ai_summary": "Test summary for verification",
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "isin": "INE123456789"
        },
        {
            "corp_id": "TEST002", 
            "title": "Test Announcement 2",
            "companyname": "Demo Corp",
            "category": "Financial Results",
            "ai_summary": "Another test summary",
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "isin": "INE987654321"
        }
    ]
    
    channel = os.getenv('SOURCE_CHANNEL', 'announcements:new')
    
    for i, announcement in enumerate(test_announcements):
        try:
            redis_client.publish(channel, json.dumps(announcement))
            logger.info(f"📤 Published test announcement {i+1}")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"❌ Failed to publish test announcement: {e}")
    
    redis_client.close()

async def main():
    \"\"\"Main entry point\"\"\"
    # Check for test mode
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        logger.info("🧪 Running in test mode - publishing sample announcements")
        await test_publisher()
        return
    
    # Normal operation
    tap = AnnouncementTap()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, tap.handle_shutdown)
    signal.signal(signal.SIGTERM, tap.handle_shutdown)
    
    # Run the tap
    success = await tap.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())