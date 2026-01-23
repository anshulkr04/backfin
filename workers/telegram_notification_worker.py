#!/usr/bin/env python3
"""
Telegram Notification Worker

Consumes notification jobs from Redis queue and sends Telegram messages.
This worker handles the async nature of Telegram notifications to avoid
blocking the main Supabase worker.
"""

import os
import sys
import time
import json
import logging
import signal
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import redis

# Local imports
from src.queue.redis_client import RedisConfig, QueueNames
from src.services.telegram.telegram_notifier import (
    get_notifier,
    send_announcement_notification
)

# Configuration
TELEGRAM_QUEUE = "backfin:queue:telegram_notifications"
PROCESSING_LIST_PREFIX = "telegram_processing:"
FAILED_QUEUE = "backfin:queue:telegram_failed"
BRPOP_TIMEOUT = 5
MAX_RETRIES = 3
PROCESSING_TTL = 60  # seconds

# Logging
worker_id = f"telegram_worker_{os.getpid()}"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(worker_id)


class TelegramNotificationJob:
    """Job structure for Telegram notifications"""
    
    def __init__(
        self,
        job_id: str,
        notification_type: str,  # 'announcement', 'insider_trading', 'deal'
        isin: str,
        company_name: str,
        symbol: str,
        category: str = None,
        summary: str = None,
        headline: str = None,
        sentiment: str = None,
        date: str = None,
        file_url: str = None,
        corp_id: str = None,
        extra_data: Dict[str, Any] = None
    ):
        self.job_id = job_id
        self.notification_type = notification_type
        self.isin = isin
        self.company_name = company_name
        self.symbol = symbol
        self.category = category
        self.summary = summary
        self.headline = headline
        self.sentiment = sentiment
        self.date = date
        self.file_url = file_url
        self.corp_id = corp_id
        self.extra_data = extra_data or {}
        self.created_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'job_id': self.job_id,
            'notification_type': self.notification_type,
            'isin': self.isin,
            'company_name': self.company_name,
            'symbol': self.symbol,
            'category': self.category,
            'summary': self.summary,
            'headline': self.headline,
            'sentiment': self.sentiment,
            'date': self.date,
            'file_url': self.file_url,
            'corp_id': self.corp_id,
            'extra_data': self.extra_data,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TelegramNotificationJob':
        return cls(
            job_id=data.get('job_id'),
            notification_type=data.get('notification_type', 'announcement'),
            isin=data.get('isin'),
            company_name=data.get('company_name'),
            symbol=data.get('symbol'),
            category=data.get('category'),
            summary=data.get('summary'),
            headline=data.get('headline'),
            sentiment=data.get('sentiment'),
            date=data.get('date'),
            file_url=data.get('file_url'),
            corp_id=data.get('corp_id'),
            extra_data=data.get('extra_data', {})
        )
    
    def serialize(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def deserialize(cls, data: str) -> 'TelegramNotificationJob':
        return cls.from_dict(json.loads(data))


def create_telegram_job(
    isin: str,
    company_name: str,
    symbol: str,
    category: str = None,
    summary: str = None,
    headline: str = None,
    sentiment: str = None,
    date: str = None,
    file_url: str = None,
    corp_id: str = None,
    notification_type: str = 'announcement'
) -> TelegramNotificationJob:
    """Create a new Telegram notification job"""
    import uuid
    job_id = f"telegram_{corp_id or uuid.uuid4().hex[:8]}_{int(time.time())}"
    
    return TelegramNotificationJob(
        job_id=job_id,
        notification_type=notification_type,
        isin=isin,
        company_name=company_name,
        symbol=symbol,
        category=category,
        summary=summary,
        headline=headline,
        sentiment=sentiment,
        date=date,
        file_url=file_url,
        corp_id=corp_id
    )


def queue_telegram_notification(
    redis_client: redis.Redis,
    job: TelegramNotificationJob
) -> bool:
    """Add a Telegram notification job to the queue"""
    try:
        redis_client.lpush(TELEGRAM_QUEUE, job.serialize())
        logger.info(f"Queued Telegram notification job: {job.job_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to queue Telegram job: {e}")
        return False


class TelegramNotificationWorker:
    """Worker that processes Telegram notification jobs from Redis queue"""
    
    def __init__(self):
        self.worker_id = worker_id
        self.redis_config = RedisConfig()
        self.redis_client: Optional[redis.Redis] = None
        self.processing_list = f"{PROCESSING_LIST_PREFIX}{self.worker_id}"
        self.running = False
        self.jobs_processed = 0
        
        # Signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def connect_redis(self) -> bool:
        """Connect to Redis"""
        try:
            self.redis_client = self.redis_config.get_connection()
            self.redis_client.ping()
            logger.info("Connected to Redis")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False
    
    async def process_job(self, job_json: str) -> bool:
        """Process a single notification job"""
        try:
            job = TelegramNotificationJob.deserialize(job_json)
            logger.info(f"Processing job {job.job_id} for {job.company_name}")
            
            if job.notification_type == 'announcement':
                result = await send_announcement_notification(
                    isin=job.isin,
                    company_name=job.company_name,
                    symbol=job.symbol,
                    category=job.category,
                    summary=job.summary,
                    headline=job.headline,
                    sentiment=job.sentiment,
                    date=job.date,
                    file_url=job.file_url,
                    corp_id=job.corp_id
                )
                
                logger.info(
                    f"Job {job.job_id} complete: "
                    f"{result['sent']} sent, {result['failed']} failed, "
                    f"{result['total_subscribers']} total subscribers"
                )
                return True
            
            else:
                logger.warning(f"Unknown notification type: {job.notification_type}")
                return False
                
        except Exception as e:
            logger.exception(f"Error processing job: {e}")
            return False
    
    def get_job(self) -> Optional[str]:
        """Get next job from queue with atomic move to processing list"""
        try:
            # BRPOPLPUSH atomically moves job from main queue to processing list
            result = self.redis_client.brpoplpush(
                TELEGRAM_QUEUE,
                self.processing_list,
                timeout=BRPOP_TIMEOUT
            )
            return result
        except Exception as e:
            logger.error(f"Error getting job: {e}")
            return None
    
    def complete_job(self, job_json: str):
        """Remove completed job from processing list"""
        try:
            self.redis_client.lrem(self.processing_list, 1, job_json)
        except Exception as e:
            logger.warning(f"Error removing job from processing list: {e}")
    
    def fail_job(self, job_json: str, error: str):
        """Move failed job to failed queue"""
        try:
            # Add error info
            try:
                job_data = json.loads(job_json)
                job_data['error'] = error
                job_data['failed_at'] = datetime.utcnow().isoformat()
                job_json = json.dumps(job_data)
            except:
                pass
            
            self.redis_client.lpush(FAILED_QUEUE, job_json)
            self.redis_client.lrem(self.processing_list, 1, job_json)
            logger.warning(f"Moved job to failed queue: {error}")
        except Exception as e:
            logger.error(f"Error moving job to failed queue: {e}")
    
    async def run_async(self):
        """Main async worker loop"""
        logger.info(f"Starting Telegram notification worker: {self.worker_id}")
        
        if not self.connect_redis():
            logger.error("Failed to connect to Redis, exiting")
            return
        
        self.running = True
        
        while self.running:
            try:
                # Get job from queue
                job_json = self.get_job()
                
                if not job_json:
                    continue
                
                # Process the job
                try:
                    success = await self.process_job(job_json)
                    
                    if success:
                        self.complete_job(job_json)
                        self.jobs_processed += 1
                    else:
                        self.fail_job(job_json, "Processing returned False")
                        
                except Exception as e:
                    logger.exception(f"Job processing error: {e}")
                    self.fail_job(job_json, str(e))
                
            except Exception as e:
                logger.exception(f"Worker loop error: {e}")
                time.sleep(5)  # Back off on errors
        
        logger.info(f"Worker stopped. Processed {self.jobs_processed} jobs.")
    
    def run(self):
        """Synchronous run method"""
        asyncio.run(self.run_async())


def main():
    """Main entry point"""
    # Check for required environment variables
    if not os.getenv('TELEGRAM_BOT_TOKEN'):
        logger.error("TELEGRAM_BOT_TOKEN is required")
        sys.exit(1)
    
    worker = TelegramNotificationWorker()
    worker.run()


if __name__ == "__main__":
    main()
