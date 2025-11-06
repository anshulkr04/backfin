from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any

from auth.jwt_handler import get_current_user
from services.supabase_client import supabase_service
from services.task_manager import TaskManager
from services.reclaim_service import ReclaimService
from services.websocket_manager import WebSocketManager

router = APIRouter()

# These will be injected from main.py
task_manager: TaskManager = None
reclaim_service: ReclaimService = None
websocket_manager: WebSocketManager = None

def get_task_manager():
    global task_manager
    if not task_manager:
        raise HTTPException(status_code=500, detail="Task manager not initialized")
    return task_manager

def get_reclaim_service():
    global reclaim_service
    if not reclaim_service:
        raise HTTPException(status_code=500, detail="Reclaim service not initialized")
    return reclaim_service

def get_websocket_manager():
    global websocket_manager
    if not websocket_manager:
        raise HTTPException(status_code=500, detail="WebSocket manager not initialized")
    return websocket_manager

@router.get("/stats")
async def get_admin_stats(current_user: dict = Depends(get_current_user)):
    """Get comprehensive admin statistics"""
    try:
        # Get queue stats from database
        queue_stats = await supabase_service.get_queue_stats()
        
        # Get Redis stream info
        tm = get_task_manager()
        stream_info = await tm.get_stream_info()
        consumer_info = await tm.get_consumer_info()
        pending_tasks = await tm.get_pending_tasks()
        
        # Get reclaim service stats
        rs = get_reclaim_service()
        reclaim_stats = await rs.get_reclaim_stats()
        
        # Get WebSocket stats
        wm = get_websocket_manager()
        websocket_connections = wm.get_connection_count()
        
        # Active users (consumers active in last minute)
        active_consumers = [c for c in consumer_info if c["idle_time"] < 60000]
        
        return {
            "queue_stats": queue_stats,
            "redis_stats": {
                "stream_length": stream_info.get("stream_length", 0),
                "total_entries": stream_info.get("total_entries", 0),
                "consumer_groups": stream_info.get("consumer_groups", 0),
                "total_consumers": len(consumer_info),
                "active_consumers": len(active_consumers),
                "pending_tasks": len(pending_tasks)
            },
            "reclaim_stats": reclaim_stats,
            "websocket_stats": {
                "active_connections": websocket_connections
            },
            "active_users": [
                {
                    "consumer_name": c["name"],
                    "pending_count": c["pending_count"],
                    "idle_time_ms": c["idle_time"]
                }
                for c in active_consumers
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get admin stats: {str(e)}"
        )

@router.get("/tasks")
async def get_all_tasks(
    status_filter: str = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Get all verification tasks with optional filtering"""
    try:
        query = supabase_service.client.table("verification_tasks").select(
            "*, admin_users!verification_tasks_assigned_to_user_fkey(name, email)"
        )
        
        if status_filter:
            query = query.eq("status", status_filter)
        
        result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        
        return {
            "tasks": result.data,
            "count": len(result.data),
            "offset": offset,
            "limit": limit
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tasks: {str(e)}"
        )

@router.post("/tasks/{task_id}/reassign")
async def reassign_task(
    task_id: str,
    target_user_id: str = None,
    current_user: dict = Depends(get_current_user)
):
    """Force reassign a task (admin only)"""
    try:
        # Release the task first
        await supabase_service.release_task(task_id)
        
        # If target_user_id is provided, assign to that user
        if target_user_id:
            # This would require additional logic to assign to specific user
            # For now, just release back to queue
            pass
        
        # Log the admin action
        await supabase_service.log_activity(
            user_id=current_user["user_id"],
            session_id=current_user["session_id"],
            action="admin_reassign_task",
            resource_type="task",
            resource_id=task_id,
            details={"target_user_id": target_user_id}
        )
        
        return {"message": "Task reassigned successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reassign task: {str(e)}"
        )

@router.post("/reclaim/manual")
async def manual_reclaim(current_user: dict = Depends(get_current_user)):
    """Manually trigger task reclaim process"""
    try:
        rs = get_reclaim_service()
        result = await rs.manual_reclaim()
        
        # Log the admin action
        await supabase_service.log_activity(
            user_id=current_user["user_id"],
            session_id=current_user["session_id"],
            action="admin_manual_reclaim",
            resource_type="system",
            details=result
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger manual reclaim: {str(e)}"
        )

@router.get("/users")
async def get_all_users(current_user: dict = Depends(get_current_user)):
    """Get all admin users"""
    try:
        result = supabase_service.client.table("admin_users").select(
            "id, email, name, is_active, is_verified, created_at"
        ).order("created_at", desc=True).execute()
        
        return {"users": result.data}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get users: {str(e)}"
        )

@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Deactivate a user account"""
    try:
        # Prevent self-deactivation
        if user_id == current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account"
            )
        
        # Deactivate user
        result = supabase_service.client.table("admin_users").update({
            "is_active": False
        }).eq("id", user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Deactivate all user sessions
        supabase_service.client.table("admin_sessions").update({
            "is_active": False
        }).eq("user_id", user_id).execute()
        
        # Force reclaim any assigned tasks
        rs = get_reclaim_service()
        # Note: This would need the session_id, which we don't have here
        # For now, let the normal reclaim process handle it
        
        # Log the admin action
        await supabase_service.log_activity(
            user_id=current_user["user_id"],
            session_id=current_user["session_id"],
            action="admin_deactivate_user",
            resource_type="user",
            resource_id=user_id
        )
        
        return {"message": "User deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate user: {str(e)}"
        )

@router.get("/activity")
async def get_activity_log(
    limit: int = 100,
    offset: int = 0,
    user_id: str = None,
    action: str = None,
    current_user: dict = Depends(get_current_user)
):
    """Get admin activity log"""
    try:
        query = supabase_service.client.table("admin_activity_log").select(
            "*, admin_users!admin_activity_log_user_id_fkey(name, email)"
        )
        
        if user_id:
            query = query.eq("user_id", user_id)
        
        if action:
            query = query.eq("action", action)
        
        result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        
        return {
            "activities": result.data,
            "count": len(result.data),
            "offset": offset,
            "limit": limit
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get activity log: {str(e)}"
        )

@router.post("/broadcast")
async def broadcast_message(
    message: str,
    message_type: str = "info",
    current_user: dict = Depends(get_current_user)
):
    """Broadcast a message to all connected users"""
    try:
        wm = get_websocket_manager()
        await wm.send_system_message(message, message_type)
        
        # Log the admin action
        await supabase_service.log_activity(
            user_id=current_user["user_id"],
            session_id=current_user["session_id"],
            action="admin_broadcast_message",
            resource_type="system",
            details={"message": message, "message_type": message_type}
        )
        
        return {"message": "Broadcast sent successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to broadcast message: {str(e)}"
        )

@router.get("/system/health")
async def system_health(current_user: dict = Depends(get_current_user)):
    """Get system health status"""
    try:
        # Check Redis connection
        tm = get_task_manager()
        redis_healthy = True
        try:
            await tm.redis_client.ping()
        except:
            redis_healthy = False
        
        # Check database connection
        db_healthy = True
        try:
            supabase_service.client.table("admin_users").select("id").limit(1).execute()
        except:
            db_healthy = False
        
        # Check services
        rs = get_reclaim_service()
        wm = get_websocket_manager()
        
        return {
            "overall_health": "healthy" if redis_healthy and db_healthy else "unhealthy",
            "components": {
                "redis": "healthy" if redis_healthy else "unhealthy",
                "database": "healthy" if db_healthy else "unhealthy",
                "reclaim_service": "running" if rs.is_running else "stopped",
                "websocket_service": "running" if wm.is_running else "stopped"
            },
            "stats": {
                "websocket_connections": wm.get_connection_count(),
                "reclaim_interval": rs.reclaim_interval,
                "task_timeout_minutes": rs.task_timeout_minutes
            }
        }
        
    except Exception as e:
        return {
            "overall_health": "error",
            "error": str(e)
        }