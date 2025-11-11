import asyncio
import logging
from datetime import datetime
from typing import Optional

from services.task_manager import TaskManager
from services.supabase_client import supabase_service

logger = logging.getLogger(__name__)

class ReclaimService:
    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager
        self.reclaim_interval = 120  # Check every 2 minutes
        self.task_timeout_minutes = 10  # Tasks timeout after 10 minutes
        self.is_running = False
        self.reclaim_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the reclaim service"""
        if self.is_running:
            logger.warning("⚠️ Reclaim service is already running")
            return
        
        self.is_running = True
        self.reclaim_task = asyncio.create_task(self.reclaim_loop())
        logger.info(f"🔄 Started reclaim service (checking every {self.reclaim_interval}s, timeout: {self.task_timeout_minutes}m)")
    
    async def stop(self):
        """Stop the reclaim service"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.reclaim_task:
            self.reclaim_task.cancel()
            try:
                await self.reclaim_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 Stopped reclaim service")
    
    async def reclaim_loop(self):
        """Main reclaim loop that runs periodically"""
        while self.is_running:
            try:
                await self.reclaim_stale_tasks()
                await asyncio.sleep(self.reclaim_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in reclaim loop: {e}")
                await asyncio.sleep(self.reclaim_interval)
    
    async def reclaim_stale_tasks(self):
        """Reclaim tasks that have been idle for too long"""
        try:
            # Calculate timeout in milliseconds
            timeout_ms = self.task_timeout_minutes * 60 * 1000
            
            # Reclaim stale tasks from Redis Stream
            redis_reclaimed = await self.task_manager.reclaim_stale_tasks(timeout_ms)
            
            # Release stale tasks in the database
            db_released = await supabase_service.release_stale_tasks(self.task_timeout_minutes)
            
            if redis_reclaimed > 0 or db_released > 0:
                logger.info(f"🔄 Reclaimed {redis_reclaimed} Redis tasks, released {db_released} database tasks")
                
                # Log the reclaim activity
                await supabase_service.log_activity(
                    user_id="system",
                    session_id="reclaim-service",
                    action="reclaim_stale_tasks",
                    resource_type="task",
                    details={
                        "redis_reclaimed": redis_reclaimed,
                        "db_released": db_released,
                        "timeout_minutes": self.task_timeout_minutes
                    }
                )
        
        except Exception as e:
            logger.error(f"❌ Failed to reclaim stale tasks: {e}")
    
    async def force_reclaim_user_tasks(self, user_id: str, session_id: str):
        """Force reclaim all tasks for a specific user (e.g., when user logs out)"""
        try:
            # Release from Redis Stream
            redis_released = await self.task_manager.release_user_tasks(user_id, session_id)
            
            # Release from database (tasks assigned to this user)
            db_result = await supabase_service.client.table("verification_tasks").update({
                "status": "queued",
                "assigned_to_user": None,
                "assigned_to_session": None,
                "assigned_at": None
            }).eq("assigned_to_user", user_id).eq("status", "in_progress").execute()
            
            db_released = len(db_result.data) if db_result.data else 0
            
            if redis_released > 0 or db_released > 0:
                logger.info(f"🔄 Force reclaimed {redis_released} Redis tasks, {db_released} database tasks for user {user_id}")
                
                # Log the activity
                await supabase_service.log_activity(
                    user_id=user_id,
                    session_id=session_id,
                    action="force_reclaim_tasks",
                    resource_type="task",
                    details={
                        "redis_released": redis_released,
                        "db_released": db_released,
                        "reason": "user_logout_or_force_reclaim"
                    }
                )
            
            return redis_released + db_released
        
        except Exception as e:
            logger.error(f"❌ Failed to force reclaim tasks for user {user_id}: {e}")
            return 0
    
    async def get_reclaim_stats(self) -> dict:
        """Get statistics about the reclaim service"""
        try:
            # Get pending tasks info
            pending_tasks = await self.task_manager.get_pending_tasks()
            
            # Calculate stale tasks
            timeout_ms = self.task_timeout_minutes * 60 * 1000
            stale_tasks = [t for t in pending_tasks if t["idle_time_ms"] >= timeout_ms]
            
            return {
                "is_running": self.is_running,
                "reclaim_interval_seconds": self.reclaim_interval,
                "task_timeout_minutes": self.task_timeout_minutes,
                "total_pending_tasks": len(pending_tasks),
                "stale_tasks_count": len(stale_tasks),
                "next_reclaim_in_seconds": self.reclaim_interval if self.is_running else None
            }
        
        except Exception as e:
            logger.error(f"❌ Failed to get reclaim stats: {e}")
            return {
                "is_running": self.is_running,
                "error": str(e)
            }
    
    async def manual_reclaim(self) -> dict:
        """Manually trigger a reclaim operation"""
        try:
            logger.info("🔄 Manual reclaim triggered")
            await self.reclaim_stale_tasks()
            
            return {
                "success": True,
                "message": "Manual reclaim completed",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"❌ Manual reclaim failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }