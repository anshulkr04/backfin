from fastapi import APIRouter, HTTPException, status, Depends, Request
from typing import Optional

from models.verification import TaskResponse, TaskStatsResponse, FieldEditRequest, TaskVerifyRequest, TaskVerifyWithChangesRequest
from auth.jwt_handler import get_current_user

# Try to import Supabase service, fall back to mock if not available
try:
    from services.supabase_client import supabase_service
except ImportError:
    from services.mock_supabase import supabase_service

from services.task_manager import TaskManager
from services.websocket_manager import WebSocketManager

router = APIRouter()

# These will be injected from main.py
task_manager: TaskManager = None
websocket_manager: WebSocketManager = None

def get_task_manager():
    global task_manager
    if not task_manager:
        raise HTTPException(status_code=500, detail="Task manager not initialized")
    return task_manager

def get_websocket_manager():
    global websocket_manager
    if not websocket_manager:
        raise HTTPException(status_code=500, detail="WebSocket manager not initialized")
    return websocket_manager

@router.post("/claim", response_model=Optional[TaskResponse])
async def claim_next_task(
    current_user: dict = Depends(get_current_user),
    request: Request = None
):
    """Claim the next available verification task"""
    return await get_next_task(current_user, request)

@router.get("/next", response_model=Optional[TaskResponse])
async def get_next_task(
    current_user: dict = Depends(get_current_user),
    request: Request = None
):
    """Get the next available verification task"""
    user_id = current_user["user_id"]
    session_id = current_user["session_id"]
    
    try:
        # Check if user already has a task assigned
        existing_count = await supabase_service.get_user_assigned_count(user_id)
        if existing_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have a task assigned. Complete it first or release it."
            )
        
        # Try to claim a task from Redis Stream
        tm = get_task_manager()
        claimed_task = await tm.claim_next_task(user_id, session_id)
        
        if not claimed_task:
            return None  # No tasks available
        
        task_id = claimed_task["task_id"]
        
        # Assign the task in the database
        success = await supabase_service.assign_task_to_user(task_id, user_id, session_id)
        
        if not success:
            # Task might have been claimed by someone else or doesn't exist
            # Acknowledge the Redis message to remove it from pending
            await tm.acknowledge_task(claimed_task["message_id"])
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found or already assigned"
            )
        
        # Get the full task details
        task = await supabase_service.get_task_by_id(task_id)
        if not task:
            # Acknowledge and release
            await tm.acknowledge_task(claimed_task["message_id"])
            await supabase_service.release_task(task_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        # Get edit history
        edits = await supabase_service.get_task_edits(task_id)
        
        # Log activity
        await supabase_service.log_activity(
            user_id=user_id,
            session_id=session_id,
            action="claim_task",
            resource_type="task",
            resource_id=task_id,
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None
        )
        
        # Notify via WebSocket
        wm = get_websocket_manager()
        await wm.notify_task_assigned(user_id, task_id)
        
        return TaskResponse(
            id=str(task.id),
            announcement_id=str(task.announcement_id),
            original_data=task.original_data,
            current_data=task.current_data,
            has_edits=task.has_edits,
            edit_count=task.edit_count,
            status=task.status,
            assigned_to_user=str(task.assigned_to_user) if task.assigned_to_user else None,
            assigned_at=task.assigned_at,
            created_at=task.created_at,
            changes=[
                {
                    "field": edit.field_name,
                    "original": edit.original_value,
                    "current": edit.current_value,
                    "edited_by": str(edit.edited_by),
                    "edited_at": edit.edited_at,
                    "reason": edit.edit_reason
                }
                for edit in edits
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get next task: {str(e)}"
        )

@router.get("/my-current", response_model=Optional[TaskResponse])
async def get_my_current_task(current_user: dict = Depends(get_current_user)):
    """Get the current task assigned to the user"""
    user_id = current_user["user_id"]
    
    try:
        # Find user's current task
        result = await supabase_service.client.table("verification_tasks").select("*").eq(
            "assigned_to_user", user_id
        ).eq("status", "in_progress").execute()
        
        if not result.data:
            return None
        
        task_data = result.data[0]
        task_id = task_data["id"]
        
        # Get edit history
        edits = await supabase_service.get_task_edits(task_id)
        
        return TaskResponse(
            id=task_id,
            announcement_id=task_data["announcement_id"],
            original_data=task_data["original_data"],
            current_data=task_data["current_data"],
            has_edits=task_data["has_edits"],
            edit_count=task_data["edit_count"],
            status=task_data["status"],
            assigned_to_user=task_data["assigned_to_user"],
            assigned_at=task_data["assigned_at"],
            created_at=task_data["created_at"],
            changes=[
                {
                    "field": edit.field_name,
                    "original": edit.original_value,
                    "current": edit.current_value,
                    "edited_by": str(edit.edited_by),
                    "edited_at": edit.edited_at,
                    "reason": edit.edit_reason
                }
                for edit in edits
            ]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get current task: {str(e)}"
        )

@router.put("/{task_id}/field")
async def edit_task_field(
    task_id: str,
    edit_request: FieldEditRequest,
    current_user: dict = Depends(get_current_user),
    request: Request = None
):
    """Edit a field in the verification task"""
    user_id = current_user["user_id"]
    session_id = current_user["session_id"]
    
    try:
        # Verify user has this task assigned
        task = await supabase_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        if str(task.assigned_to_user) != user_id or task.status != "in_progress":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Task is not assigned to you or not in progress"
            )
        
        # Update the field
        await supabase_service.update_task_field(
            task_id=task_id,
            field_name=edit_request.field,
            new_value=edit_request.value,
            user_id=user_id,
            reason=edit_request.reason
        )
        
        # Log activity
        await supabase_service.log_activity(
            user_id=user_id,
            session_id=session_id,
            action="edit_field",
            resource_type="task",
            resource_id=task_id,
            details={
                "field": edit_request.field,
                "new_value": edit_request.value,
                "reason": edit_request.reason
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None
        )
        
        return {"message": "Field updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to edit field: {str(e)}"
        )

@router.post("/{task_id}/verify")
async def verify_task(
    task_id: str,
    verify_request: TaskVerifyWithChangesRequest,
    current_user: dict = Depends(get_current_user),
    request: Request = None
):
    """Submit verification for a task"""
    user_id = current_user["user_id"]
    session_id = current_user["session_id"]
    
    try:
        # Verify user has this task assigned
        task = await supabase_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        if str(task.assigned_to_user) != user_id or task.status != "in_progress":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Task is not assigned to you or not in progress"
            )
        
        # Apply any field changes first
        if verify_request.changes:
            for field_name, new_value in verify_request.changes.items():
                await supabase_service.update_task_field(
                    task_id=task_id,
                    field_name=field_name,
                    new_value=new_value,
                    user_id=user_id,
                    reason=f"Updated during {verify_request.action} action"
                )
        
        # Determine verification status based on action
        is_verified = verify_request.action in ["approved", "approved_with_changes"]
        
        # Complete the verification
        success = await supabase_service.complete_verification(
            task_id=task_id,
            user_id=user_id,
            is_verified=is_verified,
            notes=verify_request.notes or f"Action: {verify_request.action}"
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to complete verification"
            )
        
        # Log activity
        await supabase_service.log_activity(
            user_id=user_id,
            session_id=session_id,
            action=verify_request.action,
            resource_type="task",
            resource_id=task_id,
            details={
                "verified": is_verified,
                "notes": verify_request.notes,
                "changes_made": len(verify_request.changes) > 0,
                "changes": verify_request.changes
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None
        )
        
        # Notify via WebSocket
        wm = get_websocket_manager()
        await wm.notify_task_completed(user_id, task_id, is_verified)
        
        # TODO: If verified=True, update the original Supabase record with any changes
        if is_verified and verify_request.changes:
            # This is where we'd update the original corporatefilings record
            # with the admin-approved changes
            pass
        
        return {
            "message": f"Task {verify_request.action} successfully",
            "verified": is_verified,
            "action": verify_request.action
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify task: {str(e)}"
        )

@router.post("/{task_id}/release")
async def release_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    request: Request = None
):
    """Release a task back to the queue"""
    user_id = current_user["user_id"]
    session_id = current_user["session_id"]
    
    try:
        # Verify user has this task assigned
        task = await supabase_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        if str(task.assigned_to_user) != user_id or task.status != "in_progress":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Task is not assigned to you or not in progress"
            )
        
        # Release the task
        success = await supabase_service.release_task(task_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to release task"
            )
        
        # Log activity
        await supabase_service.log_activity(
            user_id=user_id,
            session_id=session_id,
            action="release_task",
            resource_type="task",
            resource_id=task_id,
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None
        )
        
        return {"message": "Task released successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to release task: {str(e)}"
        )

@router.get("/stats", response_model=TaskStatsResponse)
async def get_task_stats(current_user: dict = Depends(get_current_user)):
    """Get verification task statistics"""
    user_id = current_user["user_id"]
    
    try:
        # Get general stats
        stats = await supabase_service.get_queue_stats()
        
        # Get user's assigned count
        my_assigned = await supabase_service.get_user_assigned_count(user_id)
        
        return TaskStatsResponse(
            pending_count=stats["pending_count"],
            in_progress_count=stats["in_progress_count"],
            verified_today=stats["verified_today"],
            verified_yes_today=stats["verified_yes_today"],
            verified_no_today=stats["verified_no_today"],
            total_tasks=stats["total_tasks"],
            my_assigned_count=my_assigned
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task stats: {str(e)}"
        )