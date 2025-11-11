from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import HTMLResponse
from typing import List, Dict, Any

from auth.jwt_handler import get_current_user

# Try to import Supabase service, fall back to mock if not available
try:
    from services.supabase_client import supabase_service
except ImportError:
    from services.mock_supabase import supabase_service

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

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard():
    """Serve admin dashboard HTML"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Verification Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .header { background: #007bff; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
            .stat-card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .stat-number { font-size: 2em; font-weight: bold; color: #007bff; }
            .task { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 8px; background: white; }
            .pending { border-left: 4px solid #ffc107; }
            .in_progress { border-left: 4px solid #17a2b8; }
            .verified { border-left: 4px solid #28a745; }
            .rejected { border-left: 4px solid #dc3545; }
            button { padding: 8px 15px; margin: 5px; border: none; border-radius: 4px; cursor: pointer; }
            .claim-btn { background-color: #007bff; color: white; }
            .approve-btn { background-color: #28a745; color: white; }
            .reject-btn { background-color: #dc3545; color: white; }
            .release-btn { background-color: #6c757d; color: white; }
            textarea { width: 100%; height: 80px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; padding: 8px; }
            .task-content { margin: 10px 0; }
            .task-meta { font-size: 0.9em; color: #666; }
            .nav { display: flex; gap: 10px; margin-bottom: 20px; }
            .nav button { background: #6c757d; color: white; }
            .nav button.active { background: #007bff; }
            .loading { text-align: center; padding: 20px; color: #666; }
            .error { background: #f8d7da; color: #721c24; padding: 10px; border-radius: 4px; margin: 10px 0; }
            .success { background: #d4edda; color: #155724; padding: 10px; border-radius: 4px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🛡️ Admin Verification Dashboard</h1>
            <p>Manage and verify AI-processed announcements</p>
        </div>
        
        <div class="nav">
            <button onclick="showSection('overview')" class="active" id="overview-btn">Overview</button>
            <button onclick="showSection('tasks')" id="tasks-btn">Tasks</button>
            <button onclick="showSection('my-task')" id="my-task-btn">My Current Task</button>
            <button onclick="logout()">Logout</button>
        </div>
        
        <div id="message"></div>
        
        <div id="overview-section">
            <div class="stats" id="stats"></div>
        </div>
        
        <div id="tasks-section" style="display:none;">
            <div class="loading">Loading tasks...</div>
            <div id="tasks-list"></div>
        </div>
        
        <div id="my-task-section" style="display:none;">
            <div id="current-task"></div>
        </div>
        
        <script>
            let token = localStorage.getItem('adminToken');
            let ws = null;
            let currentSection = 'overview';
            
            if (!token) {
                window.location.href = '/auth/login';
            }
            
            // WebSocket connection
            function connectWebSocket() {
                ws = new WebSocket(`ws://localhost:9000/ws?token=${token}`);
                
                ws.onopen = function() {
                    console.log('WebSocket connected');
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    console.log('WebSocket message:', data);
                    
                    if (data.type === 'stats_update') {
                        updateStats(data.data);
                    } else if (data.type === 'task_update') {
                        loadCurrentData();
                    }
                };
                
                ws.onclose = function() {
                    console.log('WebSocket disconnected');
                    setTimeout(connectWebSocket, 5000); // Reconnect after 5 seconds
                };
            }
            
            async function apiCall(endpoint, options = {}) {
                const response = await fetch(`http://localhost:9000${endpoint}`, {
                    ...options,
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json',
                        ...options.headers
                    }
                });
                
                if (!response.ok) {
                    throw new Error(`API call failed: ${response.statusText}`);
                }
                
                return response.json();
            }
            
            function showMessage(text, type = 'info') {
                const messageDiv = document.getElementById('message');
                messageDiv.innerHTML = `<div class="${type}">${text}</div>`;
                setTimeout(() => messageDiv.innerHTML = '', 5000);
            }
            
            function showSection(section) {
                // Hide all sections
                document.querySelectorAll('[id$="-section"]').forEach(el => el.style.display = 'none');
                document.querySelectorAll('.nav button').forEach(btn => btn.classList.remove('active'));
                
                // Show selected section
                document.getElementById(`${section}-section`).style.display = 'block';
                document.getElementById(`${section}-btn`).classList.add('active');
                
                currentSection = section;
                loadCurrentData();
            }
            
            function updateStats(stats) {
                const container = document.getElementById('stats');
                container.innerHTML = `
                    <div class="stat-card">
                        <div class="stat-number">${stats.pending_count || 0}</div>
                        <div>Pending Tasks</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${stats.in_progress_count || 0}</div>
                        <div>In Progress</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${stats.verified_today || 0}</div>
                        <div>Verified Today</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${stats.my_assigned_count || 0}</div>
                        <div>My Current Tasks</div>
                    </div>
                `;
            }
            
            async function loadStats() {
                try {
                    const stats = await apiCall('/tasks/stats');
                    updateStats(stats);
                } catch (error) {
                    console.error('Error loading stats:', error);
                }
            }
            
            async function loadTasks() {
                try {
                    const response = await apiCall('/admin/tasks?limit=50');
                    const tasks = response.tasks;
                    
                    const container = document.getElementById('tasks-list');
                    if (tasks.length === 0) {
                        container.innerHTML = '<div class="loading">No tasks available</div>';
                        return;
                    }
                    
                    container.innerHTML = tasks.map(task => `
                        <div class="task ${task.status}" id="task-${task.id}">
                            <div class="task-meta">
                                <strong>ID:</strong> ${task.id} | 
                                <strong>Status:</strong> ${task.status} | 
                                <strong>Created:</strong> ${new Date(task.created_at).toLocaleString()}
                                ${task.assigned_to_user ? ` | <strong>Assigned to:</strong> ${task.admin_users?.name || 'Unknown'}` : ''}
                            </div>
                            <div class="task-content">
                                <strong>Original Data:</strong>
                                <textarea readonly>${JSON.stringify(task.original_data, null, 2)}</textarea>
                                ${task.current_data && JSON.stringify(task.current_data) !== JSON.stringify(task.original_data) ? `
                                    <strong>Current Data:</strong>
                                    <textarea readonly>${JSON.stringify(task.current_data, null, 2)}</textarea>
                                ` : ''}
                            </div>
                            <div>
                                ${task.status === 'pending' && !task.assigned_to_user ? 
                                    `<button class="claim-btn" onclick="claimTask('${task.id}')">Claim Task</button>` : ''
                                }
                                ${task.status === 'in_progress' && task.assigned_to_user ? 
                                    `<button class="release-btn" onclick="releaseTask('${task.id}')">Release Task</button>` : ''
                                }
                            </div>
                        </div>
                    `).join('');
                } catch (error) {
                    console.error('Error loading tasks:', error);
                    document.getElementById('tasks-list').innerHTML = '<div class="error">Error loading tasks</div>';
                }
            }
            
            async function loadMyTask() {
                try {
                    const task = await apiCall('/tasks/my-current');
                    const container = document.getElementById('current-task');
                    
                    if (!task) {
                        container.innerHTML = `
                            <div class="loading">No task currently assigned</div>
                            <button class="claim-btn" onclick="claimNextTask()">Claim Next Task</button>
                        `;
                        return;
                    }
                    
                    container.innerHTML = `
                        <div class="task ${task.status}">
                            <div class="task-meta">
                                <strong>Task ID:</strong> ${task.id} | 
                                <strong>Status:</strong> ${task.status} | 
                                <strong>Assigned:</strong> ${new Date(task.assigned_at).toLocaleString()}
                            </div>
                            <div class="task-content">
                                <strong>Original Data:</strong>
                                <textarea id="original-data" readonly>${JSON.stringify(task.original_data, null, 2)}</textarea>
                                
                                <strong>Current Data (editable):</strong>
                                <textarea id="current-data">${JSON.stringify(task.current_data, null, 2)}</textarea>
                                
                                <strong>Verification Notes:</strong>
                                <textarea id="notes" placeholder="Add your verification notes here..."></textarea>
                            </div>
                            <div>
                                <button class="approve-btn" onclick="verifyTask('${task.id}', 'approved')">Approve</button>
                                <button class="approve-btn" onclick="verifyTask('${task.id}', 'approved_with_changes')">Approve with Changes</button>
                                <button class="reject-btn" onclick="verifyTask('${task.id}', 'rejected')">Reject</button>
                                <button class="release-btn" onclick="releaseTask('${task.id}')">Release</button>
                            </div>
                        </div>
                    `;
                } catch (error) {
                    console.error('Error loading my task:', error);
                    document.getElementById('current-task').innerHTML = '<div class="error">Error loading current task</div>';
                }
            }
            
            async function claimNextTask() {
                try {
                    const task = await apiCall('/tasks/claim', { method: 'POST' });
                    if (task) {
                        showMessage('Task claimed successfully!', 'success');
                        loadCurrentData();
                    } else {
                        showMessage('No tasks available to claim', 'info');
                    }
                } catch (error) {
                    console.error('Error claiming task:', error);
                    showMessage('Error claiming task: ' + error.message, 'error');
                }
            }
            
            async function claimTask(taskId) {
                try {
                    await claimNextTask(); // Use the existing claim logic
                } catch (error) {
                    console.error('Error claiming task:', error);
                    showMessage('Error claiming task', 'error');
                }
            }
            
            async function releaseTask(taskId) {
                try {
                    await apiCall(`/tasks/${taskId}/release`, { method: 'POST' });
                    showMessage('Task released successfully!', 'success');
                    loadCurrentData();
                } catch (error) {
                    console.error('Error releasing task:', error);
                    showMessage('Error releasing task', 'error');
                }
            }
            
            async function verifyTask(taskId, action) {
                try {
                    const currentDataText = document.getElementById('current-data').value;
                    const notes = document.getElementById('notes').value;
                    
                    let currentData = {};
                    try {
                        currentData = JSON.parse(currentDataText);
                    } catch (e) {
                        showMessage('Invalid JSON in current data field', 'error');
                        return;
                    }
                    
                    const payload = {
                        action: action,
                        notes: notes,
                        changes: currentData // This should be a diff, but for simplicity we're sending the full object
                    };
                    
                    await apiCall(`/tasks/${taskId}/verify`, {
                        method: 'POST',
                        body: JSON.stringify(payload)
                    });
                    
                    showMessage(`Task ${action} successfully!`, 'success');
                    loadCurrentData();
                } catch (error) {
                    console.error('Error verifying task:', error);
                    showMessage('Error verifying task', 'error');
                }
            }
            
            function loadCurrentData() {
                if (currentSection === 'overview') {
                    loadStats();
                } else if (currentSection === 'tasks') {
                    loadTasks();
                } else if (currentSection === 'my-task') {
                    loadMyTask();
                }
            }
            
            function logout() {
                localStorage.removeItem('adminToken');
                if (ws) ws.close();
                window.location.href = '/auth/login';
            }
            
            // Initialize
            connectWebSocket();
            loadCurrentData();
            
            // Auto-refresh every 30 seconds
            setInterval(loadCurrentData, 30000);
        </script>
    </body>
    </html>
    """
    return html

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