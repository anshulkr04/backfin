#!/usr/bin/env python3
"""
Queue Management System for verification tasks
Handles orphaned tasks, timeouts, session cleanup, and retry logic
"""

import os
import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass

from core.database import DatabaseManager, TaskStatus
from core.redis_coordinator import RedisCoordinator

logger = logging.getLogger(__name__)

@dataclass
class QueueStats:
    total_tasks: int
    queued_tasks: int
    in_progress_tasks: int
    verified_tasks: int
    orphaned_tasks_cleaned: int
    expired_sessions_cleaned: int
    timeout_tasks_released: int
    active_verifiers: int
    last_cleanup: datetime

class QueueManager:
    def __init__(self):
        self.db = DatabaseManager()
        self.redis = RedisCoordinator()
        
        # Configuration
        self.enabled = os.getenv('QUEUE_MANAGEMENT_ENABLED', 'true').lower() == 'true'
        self.cleanup_interval = int(os.getenv('QUEUE_CLEANUP_INTERVAL', '60'))  # seconds
        self.task_timeout = int(os.getenv('QUEUE_TASK_TIMEOUT', '1800'))  # 30 minutes
        self.session_timeout = int(os.getenv('QUEUE_SESSION_TIMEOUT', '3600'))  # 1 hour
        self.max_retry_count = int(os.getenv('QUEUE_MAX_RETRIES', '3'))
        
        # State
        self.running = False
        self.stats = QueueStats(
            total_tasks=0,
            queued_tasks=0,
            in_progress_tasks=0,
            verified_tasks=0,
            orphaned_tasks_cleaned=0,
            expired_sessions_cleaned=0,
            timeout_tasks_released=0,
            active_verifiers=0,
            last_cleanup=datetime.min
        )

    async def initialize(self):
        """Initialize database and Redis connections"""
        logger.info("🚀 Initializing Queue Manager")
        
        if not self.enabled:
            logger.info("⏸️ Queue management disabled by configuration")
            return False
        
        # Connect to database
        if not await self.db.connect():
            logger.error("❌ Failed to connect to database")
            return False
        
        # Connect to Redis
        if not await self.redis.connect():
            logger.error("❌ Failed to connect to Redis")
            return False
        
        logger.info("✅ Queue Manager initialized successfully")
        logger.info(f"⚙️ Configuration:")
        logger.info(f"   Cleanup interval: {self.cleanup_interval}s")
        logger.info(f"   Task timeout: {self.task_timeout}s")
        logger.info(f"   Session timeout: {self.session_timeout}s")
        logger.info(f"   Max retries: {self.max_retry_count}")
        
        return True

    async def cleanup_orphaned_tasks(self) -> int:
        """Clean up tasks assigned to inactive sessions"""
        try:
            # Get active session IDs from Redis
            active_session_ids = await self.redis.get_active_session_ids()
            
            # Clean up orphaned tasks in database
            orphaned_count = await self.db.cleanup_orphaned_tasks(active_session_ids)
            
            if orphaned_count > 0:
                logger.info(f"🧹 Released {orphaned_count} orphaned tasks")
                
                # Notify about released tasks
                await self.redis.publish_system_broadcast({
                    'type': 'tasks_released',
                    'count': orphaned_count,
                    'reason': 'orphaned_sessions'
                })
            
            self.stats.orphaned_tasks_cleaned += orphaned_count
            return orphaned_count
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up orphaned tasks: {e}")
            return 0

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired admin sessions"""
        try:
            # Clean up expired sessions in database
            expired_count = await self.db.cleanup_expired_sessions()
            
            # Clean up inactive verifiers in Redis
            inactive_count = await self.redis.cleanup_inactive_verifiers()
            
            total_cleaned = expired_count + inactive_count
            
            if total_cleaned > 0:
                logger.info(f"🧹 Cleaned up {expired_count} expired sessions and {inactive_count} inactive verifiers")
            
            self.stats.expired_sessions_cleaned += total_cleaned
            return total_cleaned
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up expired sessions: {e}")
            return 0

    async def handle_timeout_tasks(self) -> int:
        """Handle tasks that have exceeded timeout"""
        try:
            # Calculate timeout threshold
            timeout_threshold = datetime.utcnow() - timedelta(seconds=self.task_timeout)
            
            # Get in-progress tasks that have timed out
            in_progress_tasks = await self.db.get_verification_tasks(
                status=TaskStatus.IN_PROGRESS,
                limit=1000  # Process in batches
            )
            
            timeout_count = 0
            
            for task in in_progress_tasks:
                # Check if task has timed out
                if task.assigned_at and task.assigned_at < timeout_threshold:
                    # Check retry count
                    if task.retry_count >= self.max_retry_count:
                        # Move to dead letter (verified as failed)
                        await self.db.update_verification_task(
                            task_id=task.id,
                            status=TaskStatus.VERIFIED,
                            is_verified=False,
                            verification_notes=f"Auto-rejected: Max retries exceeded ({self.max_retry_count})"
                        )
                        
                        logger.warning(f"💀 Task {task.id} moved to dead letter (max retries exceeded)")
                        
                        # Log activity
                        await self.db.log_admin_activity(
                            user_id=None,
                            session_id=None,
                            action="task_dead_lettered",
                            resource_type="verification_task",
                            resource_id=task.id,
                            details={"reason": "max_retries_exceeded", "retry_count": task.retry_count}
                        )
                    else:
                        # Release back to queue with retry increment
                        success = await self.db.release_verification_task(task.id)
                        
                        if success:
                            # Increment timeout count
                            await self.db.update_verification_task(
                                task_id=task.id,
                                retry_count=task.retry_count + 1,
                                timeout_count=task.timeout_count + 1
                            )
                            
                            timeout_count += 1
                            logger.info(f"⏰ Released timeout task {task.id} (retry {task.retry_count + 1})")
                            
                            # Notify about new available task
                            await self.redis.notify_new_task({
                                'id': task.id,
                                'announcement_id': task.announcement_id,
                                'retry_count': task.retry_count + 1,
                                'reason': 'timeout_release'
                            })
                            
                            # Log activity
                            await self.db.log_admin_activity(
                                user_id=None,
                                session_id=None,
                                action="task_timeout_released",
                                resource_type="verification_task",
                                resource_id=task.id,
                                details={"retry_count": task.retry_count + 1}
                            )
            
            if timeout_count > 0:
                logger.info(f"⏰ Released {timeout_count} timed-out tasks")
            
            self.stats.timeout_tasks_released += timeout_count
            return timeout_count
            
        except Exception as e:
            logger.error(f"❌ Error handling timeout tasks: {e}")
            return 0

    async def rebalance_tasks(self) -> bool:
        """Trigger task rebalancing among active verifiers"""
        try:
            # Get active verifiers
            active_verifiers = await self.redis.get_active_verifiers()
            
            if not active_verifiers:
                logger.debug("📭 No active verifiers for rebalancing")
                return False
            
            # Get queued tasks
            queued_tasks = await self.db.get_verification_tasks(
                status=TaskStatus.QUEUED,
                limit=100
            )
            
            if not queued_tasks:
                logger.debug("📭 No queued tasks for rebalancing")
                return False
            
            # Notify about available tasks
            for task in queued_tasks[:10]:  # Notify about first 10 tasks
                await self.redis.notify_new_task({
                    'id': task.id,
                    'announcement_id': task.announcement_id,
                    'company': task.current_data.get('companyname', 'Unknown'),
                    'category': task.current_data.get('category', 'Unknown'),
                    'created_at': task.created_at.isoformat()
                })
            
            logger.info(f"🔄 Triggered rebalancing for {len(active_verifiers)} verifiers with {len(queued_tasks)} queued tasks")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error rebalancing tasks: {e}")
            return False

    async def update_stats(self):
        """Update queue statistics"""
        try:
            # Get task counts by status
            verification_stats = await self.db.get_verification_stats()
            
            # Update stats
            self.stats.total_tasks = sum(
                verification_stats.get(f"tasks_{status.value}", 0)
                for status in TaskStatus
            )
            self.stats.queued_tasks = verification_stats.get("tasks_queued", 0)
            self.stats.in_progress_tasks = verification_stats.get("tasks_in_progress", 0)
            self.stats.verified_tasks = verification_stats.get("tasks_verified", 0)
            
            # Get active verifiers count
            active_verifiers = await self.redis.get_active_verifiers()
            self.stats.active_verifiers = len(active_verifiers)
            
            self.stats.last_cleanup = datetime.utcnow()
            
            # Update Redis stats
            await self.redis.update_stats({
                'queue_total_tasks': str(self.stats.total_tasks),
                'queue_queued_tasks': str(self.stats.queued_tasks),
                'queue_in_progress_tasks': str(self.stats.in_progress_tasks),
                'queue_verified_tasks': str(self.stats.verified_tasks),
                'queue_active_verifiers': str(self.stats.active_verifiers),
                'queue_last_cleanup': self.stats.last_cleanup.isoformat(),
                'queue_orphaned_cleaned': str(self.stats.orphaned_tasks_cleaned),
                'queue_sessions_cleaned': str(self.stats.expired_sessions_cleaned),
                'queue_timeouts_released': str(self.stats.timeout_tasks_released)
            })
            
        except Exception as e:
            logger.error(f"❌ Error updating stats: {e}")

    async def cleanup_cycle(self):
        """Perform one cleanup cycle"""
        try:
            logger.debug("🧹 Starting cleanup cycle")
            
            # 1. Clean up expired sessions first
            await self.cleanup_expired_sessions()
            
            # 2. Clean up orphaned tasks
            await self.cleanup_orphaned_tasks()
            
            # 3. Handle timeout tasks
            await self.handle_timeout_tasks()
            
            # 4. Rebalance tasks if needed
            if self.stats.queued_tasks > 0 and self.stats.active_verifiers > 0:
                await self.rebalance_tasks()
            
            # 5. Update statistics
            await self.update_stats()
            
            logger.debug("✅ Cleanup cycle completed")
            
        except Exception as e:
            logger.error(f"❌ Error in cleanup cycle: {e}")

    async def run(self):
        """Main queue management loop"""
        if not self.enabled:
            logger.info("⏸️ Queue management disabled")
            return
        
        self.running = True
        logger.info("🚀 Starting Queue Manager")
        
        try:
            while self.running:
                start_time = datetime.utcnow()
                
                # Perform cleanup cycle
                await self.cleanup_cycle()
                
                # Calculate cycle time
                cycle_time = (datetime.utcnow() - start_time).total_seconds()
                
                # Log periodic summary
                if self.stats.last_cleanup.minute % 5 == 0:  # Every 5 minutes
                    logger.info(f"📊 Queue Stats: {self.stats.queued_tasks} queued, "
                              f"{self.stats.in_progress_tasks} in progress, "
                              f"{self.stats.active_verifiers} active verifiers")
                
                # Wait for next cycle
                wait_time = max(0, self.cleanup_interval - cycle_time)
                await asyncio.sleep(wait_time)
                
        except asyncio.CancelledError:
            logger.info("🛑 Queue Manager cancelled")
        except Exception as e:
            logger.error(f"❌ Error in queue management loop: {e}")
        finally:
            self.running = False
            await self.cleanup()

    async def cleanup(self):
        """Cleanup resources"""
        logger.info("🧹 Cleaning up Queue Manager...")
        
        # Final stats update
        await self.redis.update_stats({
            'queue_manager_running': 'false',
            'queue_manager_stopped_at': datetime.utcnow().isoformat()
        })
        
        # Close connections
        await self.redis.disconnect()
        await self.db.close()
        
        # Log final stats
        logger.info("📊 Final queue management statistics:")
        logger.info(f"   Total tasks processed: {self.stats.total_tasks}")
        logger.info(f"   Orphaned tasks cleaned: {self.stats.orphaned_tasks_cleaned}")
        logger.info(f"   Expired sessions cleaned: {self.stats.expired_sessions_cleaned}")
        logger.info(f"   Timeout tasks released: {self.stats.timeout_tasks_released}")

    def stop(self):
        """Stop the queue manager"""
        logger.info("🛑 Stopping Queue Manager...")
        self.running = False

    async def get_stats(self) -> Dict[str, Any]:
        """Get current queue management statistics"""
        return {
            'total_tasks': self.stats.total_tasks,
            'queued_tasks': self.stats.queued_tasks,
            'in_progress_tasks': self.stats.in_progress_tasks,
            'verified_tasks': self.stats.verified_tasks,
            'active_verifiers': self.stats.active_verifiers,
            'orphaned_tasks_cleaned': self.stats.orphaned_tasks_cleaned,
            'expired_sessions_cleaned': self.stats.expired_sessions_cleaned,
            'timeout_tasks_released': self.stats.timeout_tasks_released,
            'last_cleanup': self.stats.last_cleanup.isoformat(),
            'running': self.running,
            'configuration': {
                'cleanup_interval': self.cleanup_interval,
                'task_timeout': self.task_timeout,
                'session_timeout': self.session_timeout,
                'max_retry_count': self.max_retry_count
            }
        }

    # ============================================================================
    # Manual Operations
    # ============================================================================
    
    async def force_cleanup_all(self) -> Dict[str, int]:
        """Force cleanup of all orphaned resources"""
        logger.info("🧹 Forcing cleanup of all orphaned resources")
        
        results = {
            'orphaned_tasks': await self.cleanup_orphaned_tasks(),
            'expired_sessions': await self.cleanup_expired_sessions(),
            'timeout_tasks': await self.handle_timeout_tasks()
        }
        
        await self.update_stats()
        
        logger.info(f"✅ Force cleanup completed: {results}")
        return results

    async def reset_task_retries(self, max_retries: int = None) -> int:
        """Reset retry counts for tasks that haven't exceeded max retries"""
        try:
            max_retries = max_retries or self.max_retry_count
            
            # This would require a custom database method
            # For now, log the operation
            logger.info(f"🔄 Reset retry counts for tasks with < {max_retries} retries")
            
            return 0  # Placeholder
            
        except Exception as e:
            logger.error(f"❌ Error resetting task retries: {e}")
            return 0

    async def requeue_failed_tasks(self) -> int:
        """Requeue verified=false tasks back to the queue"""
        try:
            # Get failed tasks (verified=false)
            failed_tasks = await self.db.get_verification_tasks(
                status=TaskStatus.VERIFIED,
                limit=1000
            )
            
            requeued_count = 0
            
            for task in failed_tasks:
                if task.is_verified == False and task.retry_count < self.max_retry_count:
                    # Reset task to queued status
                    await self.db.update_verification_task(
                        task_id=task.id,
                        status=TaskStatus.QUEUED,
                        assigned_to_user=None,
                        assigned_to_session=None,
                        assigned_at=None,
                        is_verified=None,
                        verified_by=None,
                        verified_at=None,
                        verification_notes=None
                    )
                    
                    requeued_count += 1
                    
                    # Notify about new task
                    await self.redis.notify_new_task({
                        'id': task.id,
                        'announcement_id': task.announcement_id,
                        'reason': 'manual_requeue'
                    })
            
            logger.info(f"🔄 Requeued {requeued_count} failed tasks")
            return requeued_count
            
        except Exception as e:
            logger.error(f"❌ Error requeuing failed tasks: {e}")
            return 0

# ============================================================================
# Standalone Service
# ============================================================================

class QueueManagerService:
    """Standalone queue management service"""
    
    def __init__(self):
        self.queue_manager = QueueManager()
        
    async def run_service(self):
        """Run queue manager as a standalone service"""
        # Signal handlers
        def signal_handler(signum, frame):
            logger.info(f"📨 Received signal {signum}")
            self.queue_manager.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Initialize and run
        if await self.queue_manager.initialize():
            await self.queue_manager.run()
        else:
            logger.error("❌ Failed to initialize queue manager")
            sys.exit(1)

async def main():
    """Main entry point for standalone service"""
    service = QueueManagerService()
    await service.run_service()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())