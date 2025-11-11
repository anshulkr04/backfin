#!/usr/bin/env python3
"""
Admin API server for verification system
Provides REST endpoints for task management, authentication, and WebSocket coordination
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, validator
import json

from core.database import DatabaseManager, TaskStatus, VerificationTask, AdminUser, AdminSession
from core.auth import AdminAuthManager, AuthResult
from core.redis_coordinator import RedisCoordinator
from core.test_data_simulator import TestDataSimulator

logger = logging.getLogger(__name__)

# ============================================================================
# Pydantic Models
# ============================================================================

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    
    @validator('email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v

class TaskEditRequest(BaseModel):
    field_updates: Dict[str, Any]
    edit_reason: Optional[str] = None

class TaskVerificationRequest(BaseModel):
    verified: bool
    notes: Optional[str] = None

class TaskListQuery(BaseModel):
    status: Optional[str] = None
    assigned_to_me: Optional[bool] = None
    limit: int = 50
    offset: int = 0

# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"🔌 WebSocket connected: {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"🔌 WebSocket disconnected: {session_id}")

    async def send_to_session(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"❌ Error sending to {session_id}: {e}")
                self.disconnect(session_id)

    async def broadcast_to_all(self, message: dict):
        disconnected = []
        for session_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"❌ Error broadcasting to {session_id}: {e}")
                disconnected.append(session_id)
        
        for session_id in disconnected:
            self.disconnect(session_id)

# ============================================================================
# Global State
# ============================================================================

db_manager = None
auth_manager = None
redis_coordinator = None
connection_manager = None
test_simulator = None

# ============================================================================
# Application Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global db_manager, auth_manager, redis_coordinator, connection_manager, test_simulator
    
    logger.info("🚀 Starting Admin API Server")
    
    # Initialize database
    db_manager = DatabaseManager()
    if not await db_manager.connect():
        raise RuntimeError("Failed to connect to database")
    
    # Initialize auth manager
    auth_manager = AdminAuthManager(db_manager)
    
    # Initialize Redis coordinator
    redis_coordinator = RedisCoordinator()
    if not await redis_coordinator.connect():
        raise RuntimeError("Failed to connect to Redis")
    
    # Initialize connection manager
    connection_manager = ConnectionManager()
    
    # Initialize test simulator
    test_simulator = TestDataSimulator()
    if not await test_simulator.initialize():
        logger.warning("⚠️ Test simulator initialization failed (this is OK in production)")
    
    # Setup Redis message handlers
    await setup_redis_handlers()
    
    logger.info("✅ Admin API Server started successfully")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Admin API Server")
    
    if test_simulator and test_simulator.running:
        test_simulator.stop()
    
    if redis_coordinator:
        await redis_coordinator.disconnect()
    
    if db_manager:
        await db_manager.close()
    
    logger.info("✅ Admin API Server shutdown complete")

async def setup_redis_handlers():
    """Setup Redis message handlers for real-time coordination"""
    
    async def handle_new_task(message: dict):
        """Handle new task notifications"""
        await connection_manager.broadcast_to_all({
            'type': 'new_task',
            'data': message.get('data', {}),
            'timestamp': datetime.utcnow().isoformat()
        })
    
    async def handle_task_assignment(message: dict):
        """Handle task assignment notifications"""
        await connection_manager.broadcast_to_all({
            'type': 'task_assigned',
            'data': message,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    async def handle_task_completion(message: dict):
        """Handle task completion notifications"""
        await connection_manager.broadcast_to_all({
            'type': 'task_completed',
            'data': message,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    await redis_coordinator.subscribe_to_channel(
        redis_coordinator.task_notification_channel, 
        handle_new_task
    )
    
    await redis_coordinator.subscribe_to_channel(
        redis_coordinator.task_assignment_channel,
        handle_task_assignment
    )
    
    await redis_coordinator.subscribe_to_channel(
        redis_coordinator.task_completion_channel,
        handle_task_completion
    )

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Verification System Admin API",
    description="REST API for managing announcement verification tasks",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# ============================================================================
# Dependencies
# ============================================================================

async def get_current_user(request: Request, token = Depends(security)) -> tuple[AdminUser, AdminSession]:
    """Dependency to get current authenticated user"""
    authorization = request.headers.get("authorization")
    user, session = await auth_manager.get_current_user(authorization)
    
    if not user or not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user, session

async def get_optional_user(request: Request, token = Depends(security)) -> tuple[Optional[AdminUser], Optional[AdminSession]]:
    """Dependency to get current user if authenticated (optional)"""
    authorization = request.headers.get("authorization")
    user, session = await auth_manager.get_current_user(authorization)
    return user, session

# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.post("/auth/login")
async def login(request: LoginRequest, req: Request):
    """Authenticate user and create session"""
    result = await auth_manager.authenticate_user(
        email=request.email,
        password=request.password,
        user_agent=req.headers.get("user-agent"),
        ip_address=req.client.host
    )
    
    if not result.success:
        raise HTTPException(status_code=401, detail=result.error)
    
    return {
        "success": True,
        "token": result.token,
        "user": {
            "id": result.user.id,
            "email": result.user.email,
            "name": result.user.name,
            "is_verified": result.user.is_verified
        },
        "expires_at": result.session.expires_at.isoformat()
    }

@app.post("/auth/register")
async def register(request: RegisterRequest):
    """Register a new admin user"""
    # Validate password strength
    is_strong, message = auth_manager.validate_password_strength(request.password)
    if not is_strong:
        raise HTTPException(status_code=400, detail=message)
    
    # Validate email format
    if not auth_manager.validate_email_format(request.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    result = await auth_manager.register_admin_user(
        email=request.email,
        password=request.password,
        name=request.name
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return {
        "success": True,
        "user": {
            "id": result.user.id,
            "email": result.user.email,
            "name": result.user.name,
            "is_verified": result.user.is_verified
        }
    }

@app.post("/auth/logout")
async def logout(req: Request, current_user: tuple = Depends(get_current_user)):
    """Logout current user"""
    user, session = current_user
    
    authorization = req.headers.get("authorization")
    token = auth_manager.extract_token_from_header(authorization)
    
    if token:
        success = await auth_manager.logout_user(
            token=token,
            user_agent=req.headers.get("user-agent"),
            ip_address=req.client.host
        )
        
        if success:
            return {"success": True, "message": "Logged out successfully"}
    
    raise HTTPException(status_code=400, detail="Failed to logout")

@app.get("/auth/me")
async def get_me(current_user: tuple = Depends(get_current_user)):
    """Get current user information"""
    user, session = current_user
    
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_verified": user.is_verified
        },
        "session": {
            "id": session.id,
            "expires_at": session.expires_at.isoformat(),
            "last_activity": session.last_activity.isoformat()
        }
    }

# ============================================================================
# Task Management Endpoints
# ============================================================================

@app.get("/tasks")
async def get_tasks(
    status: Optional[str] = None,
    assigned_to_me: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: tuple = Depends(get_optional_user)
):
    """Get verification tasks with optional filters"""
    user, session = current_user
    
    # Convert status string to enum
    status_filter = None
    if status:
        try:
            status_filter = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    # Apply user filter if requested
    assigned_user_filter = None
    if assigned_to_me and user:
        assigned_user_filter = user.id
    
    # Get tasks from database
    tasks = await db_manager.get_verification_tasks(
        status=status_filter,
        assigned_to_user=assigned_user_filter,
        limit=limit,
        offset=offset
    )
    
    # Convert to response format
    task_list = []
    for task in tasks:
        task_data = {
            "id": task.id,
            "announcement_id": task.announcement_id,
            "status": task.status.value,
            "has_edits": task.has_edits,
            "edit_count": task.edit_count,
            "assigned_to_user": task.assigned_to_user,
            "assigned_at": task.assigned_at.isoformat() if task.assigned_at else None,
            "is_verified": task.is_verified,
            "verified_by": task.verified_by,
            "verified_at": task.verified_at.isoformat() if task.verified_at else None,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            # Include key announcement data
            "announcement_data": {
                "company": task.current_data.get("companyname", "Unknown"),
                "category": task.current_data.get("category", "Unknown"),
                "headline": task.current_data.get("headline", ""),
                "sentiment": task.current_data.get("sentiment", ""),
                "date": task.current_data.get("date", ""),
            }
        }
        task_list.append(task_data)
    
    return {
        "tasks": task_list,
        "total": len(task_list),
        "limit": limit,
        "offset": offset,
        "has_more": len(task_list) == limit
    }

@app.get("/tasks/{task_id}")
async def get_task(task_id: str, current_user: tuple = Depends(get_current_user)):
    """Get detailed information about a specific task"""
    user, session = current_user
    
    task = await db_manager.get_verification_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get edit history
    edits = await db_manager.get_verification_edits(task_id)
    
    return {
        "task": {
            "id": task.id,
            "announcement_id": task.announcement_id,
            "original_data": task.original_data,
            "current_data": task.current_data,
            "status": task.status.value,
            "has_edits": task.has_edits,
            "edit_count": task.edit_count,
            "assigned_to_user": task.assigned_to_user,
            "assigned_to_session": task.assigned_to_session,
            "assigned_at": task.assigned_at.isoformat() if task.assigned_at else None,
            "is_verified": task.is_verified,
            "verified_by": task.verified_by,
            "verified_at": task.verified_at.isoformat() if task.verified_at else None,
            "verification_notes": task.verification_notes,
            "retry_count": task.retry_count,
            "timeout_count": task.timeout_count,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat()
        },
        "edits": [
            {
                "id": edit.id,
                "field_name": edit.field_name,
                "original_value": edit.original_value,
                "current_value": edit.current_value,
                "edited_by": edit.edited_by,
                "edited_at": edit.edited_at.isoformat(),
                "edit_reason": edit.edit_reason
            }
            for edit in edits
        ]
    }

@app.put("/tasks/{task_id}/claim")
async def claim_task(task_id: str, current_user: tuple = Depends(get_current_user)):
    """Claim a specific task for verification"""
    user, session = current_user
    
    # Try to claim the task atomically
    task = await db_manager.claim_verification_task(user.id, session.id)
    
    if not task:
        raise HTTPException(status_code=409, detail="Task not available for claiming")
    
    # Register verifier presence in Redis
    await redis_coordinator.register_verifier_presence(
        session_id=session.id,
        user_id=user.id,
        user_name=user.name
    )
    
    # Notify about assignment
    await redis_coordinator.notify_task_assignment(task.id, session.id, user.name)
    
    # Log activity
    await db_manager.log_admin_activity(
        user_id=user.id,
        session_id=session.id,
        action="task_claimed",
        resource_type="verification_task",
        resource_id=task.id
    )
    
    return {"success": True, "task_id": task.id}

@app.put("/tasks/{task_id}/edit")
async def edit_task(task_id: str, request: TaskEditRequest, current_user: tuple = Depends(get_current_user)):
    """Edit announcement data in a verification task"""
    user, session = current_user
    
    # Get current task
    task = await db_manager.get_verification_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check if task is assigned to current user
    if task.assigned_to_user != user.id:
        raise HTTPException(status_code=403, detail="Task not assigned to you")
    
    # Apply field updates
    updated_data = task.current_data.copy()
    edit_records = []
    
    for field_name, new_value in request.field_updates.items():
        if field_name not in updated_data:
            raise HTTPException(status_code=400, detail=f"Invalid field: {field_name}")
        
        original_value = updated_data.get(field_name)
        
        # Only create edit record if value actually changed
        if original_value != new_value:
            updated_data[field_name] = new_value
            
            # Create edit record
            edit = await db_manager.create_verification_edit(
                task_id=task_id,
                field_name=field_name,
                original_value=str(original_value) if original_value is not None else None,
                current_value=str(new_value) if new_value is not None else None,
                edited_by=user.id,
                edit_reason=request.edit_reason
            )
            
            edit_records.append(edit)
    
    # Update task with new data
    if edit_records:
        updated_task = await db_manager.update_verification_task(
            task_id=task_id,
            current_data=updated_data
        )
        
        # Log activity
        await db_manager.log_admin_activity(
            user_id=user.id,
            session_id=session.id,
            action="task_edited",
            resource_type="verification_task",
            resource_id=task_id,
            details={"fields_edited": list(request.field_updates.keys())}
        )
        
        return {"success": True, "edits_created": len(edit_records)}
    
    return {"success": True, "edits_created": 0, "message": "No changes detected"}

@app.put("/tasks/{task_id}/verify")
async def verify_task(task_id: str, request: TaskVerificationRequest, current_user: tuple = Depends(get_current_user)):
    """Mark a task as verified or rejected"""
    user, session = current_user
    
    # Get current task
    task = await db_manager.get_verification_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check if task is assigned to current user
    if task.assigned_to_user != user.id:
        raise HTTPException(status_code=403, detail="Task not assigned to you")
    
    # Update task status
    updated_task = await db_manager.update_verification_task(
        task_id=task_id,
        status=TaskStatus.VERIFIED,
        is_verified=request.verified,
        verified_by=user.id,
        verification_notes=request.notes
    )
    
    if not updated_task:
        raise HTTPException(status_code=500, detail="Failed to update task")
    
    # Notify about completion
    action = "approved" if request.verified else "rejected"
    await redis_coordinator.notify_task_completion(task_id, session.id, action, user.name)
    
    # Log activity
    await db_manager.log_admin_activity(
        user_id=user.id,
        session_id=session.id,
        action="task_verified",
        resource_type="verification_task",
        resource_id=task_id,
        details={"verified": request.verified, "action": action}
    )
    
    return {"success": True, "action": action}

@app.put("/tasks/{task_id}/release")
async def release_task(task_id: str, current_user: tuple = Depends(get_current_user)):
    """Release a task back to the queue"""
    user, session = current_user
    
    # Get current task
    task = await db_manager.get_verification_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check if task is assigned to current user
    if task.assigned_to_user != user.id:
        raise HTTPException(status_code=403, detail="Task not assigned to you")
    
    # Release task
    success = await db_manager.release_verification_task(task_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to release task")
    
    # Notify about release
    await redis_coordinator.notify_task_completion(task_id, session.id, "released", user.name)
    
    # Log activity
    await db_manager.log_admin_activity(
        user_id=user.id,
        session_id=session.id,
        action="task_released",
        resource_type="verification_task",
        resource_id=task_id
    )
    
    return {"success": True}

# ============================================================================
# Statistics and Monitoring
# ============================================================================

@app.get("/stats")
async def get_stats(current_user: tuple = Depends(get_optional_user)):
    """Get system statistics"""
    # Database stats
    db_stats = await db_manager.get_verification_stats()
    
    # Redis stats
    redis_stats = await redis_coordinator.get_stats()
    
    # Active verifiers
    active_verifiers = await redis_coordinator.get_active_verifiers()
    
    # Simulator stats (if running)
    simulator_stats = {}
    if test_simulator:
        simulator_stats = await test_simulator.get_stats()
    
    return {
        "database": db_stats,
        "redis": redis_stats,
        "active_verifiers": len(active_verifiers),
        "verifier_sessions": [
            {
                "session_id": v.session_id,
                "user_name": v.user_name,
                "connected_at": v.connected_at.isoformat(),
                "last_heartbeat": v.last_heartbeat.isoformat()
            }
            for v in active_verifiers
        ],
        "simulator": simulator_stats,
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================================
# WebSocket Endpoint
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """WebSocket endpoint for real-time updates"""
    # Validate token
    validation = await auth_manager.validate_session(token)
    if not validation.success:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    user = validation.user
    session = validation.session
    
    # Connect WebSocket
    await connection_manager.connect(websocket, session.id)
    
    # Register verifier presence
    await redis_coordinator.register_verifier_presence(
        session_id=session.id,
        user_id=user.id,
        user_name=user.name,
        ip_address=getattr(websocket.client, 'host', None)
    )
    
    try:
        # Send welcome message
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": f"Welcome {user.name}!",
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        # Handle incoming messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle heartbeat
            if message.get("type") == "heartbeat":
                await redis_coordinator.update_verifier_heartbeat(session.id)
                await websocket.send_text(json.dumps({
                    "type": "heartbeat_ack",
                    "timestamp": datetime.utcnow().isoformat()
                }))
            
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected: {session.id}")
    except Exception as e:
        logger.error(f"❌ WebSocket error for {session.id}: {e}")
    finally:
        # Cleanup
        connection_manager.disconnect(session.id)
        await redis_coordinator.remove_verifier_presence(session.id)

# ============================================================================
# Development and Testing Endpoints
# ============================================================================

@app.post("/dev/create-sample-task")
async def create_sample_task(current_user: tuple = Depends(get_current_user)):
    """Create a sample verification task for testing"""
    if not test_simulator:
        raise HTTPException(status_code=503, detail="Test simulator not available")
    
    task_id = await test_simulator.create_single_announcement()
    if not task_id:
        raise HTTPException(status_code=500, detail="Failed to create sample task")
    
    return {"success": True, "task_id": task_id}

@app.post("/dev/create-sample-batch")
async def create_sample_batch(count: int = 5, current_user: tuple = Depends(get_current_user)):
    """Create a batch of sample verification tasks"""
    if not test_simulator:
        raise HTTPException(status_code=503, detail="Test simulator not available")
    
    task_ids = await test_simulator.create_sample_batch(count)
    
    return {"success": True, "task_ids": task_ids, "count": len(task_ids)}

# ============================================================================
# Basic UI Endpoint
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def get_admin_ui():
    """Serve basic admin UI for testing"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Verification Admin</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 40px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 40px; }
            .section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
            .button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
            .button:hover { background: #0056b3; }
            .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
            .success { background: #d4edda; color: #155724; }
            .error { background: #f8d7da; color: #721c24; }
            .info { background: #d1ecf1; color: #0c5460; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📋 Verification System Admin</h1>
                <p>Basic interface for testing the verification system</p>
            </div>
            
            <div class="section">
                <h3>🔐 Authentication</h3>
                <div id="auth-section">
                    <input type="email" id="email" placeholder="Email" style="margin: 5px; padding: 8px;">
                    <input type="password" id="password" placeholder="Password" style="margin: 5px; padding: 8px;">
                    <button class="button" onclick="login()">Login</button>
                    <button class="button" onclick="register()">Register</button>
                </div>
                <div id="user-info" style="display: none;">
                    <p>Logged in as: <span id="user-name"></span></p>
                    <button class="button" onclick="logout()">Logout</button>
                </div>
            </div>
            
            <div class="section">
                <h3>📊 System Status</h3>
                <button class="button" onclick="getStats()">Refresh Stats</button>
                <div id="stats-display"></div>
            </div>
            
            <div class="section">
                <h3>📝 Tasks</h3>
                <button class="button" onclick="getTasks()">Get Tasks</button>
                <button class="button" onclick="createSampleTask()">Create Sample Task</button>
                <button class="button" onclick="createSampleBatch()">Create Sample Batch (5)</button>
                <div id="tasks-display"></div>
            </div>
            
            <div class="section">
                <h3>🔴 WebSocket Connection</h3>
                <button class="button" onclick="connectWebSocket()">Connect WebSocket</button>
                <button class="button" onclick="disconnectWebSocket()">Disconnect</button>
                <div id="ws-status" class="status info">Not connected</div>
                <div id="ws-messages"></div>
            </div>
            
            <div id="messages"></div>
        </div>
        
        <script>
            let authToken = localStorage.getItem('auth_token');
            let currentUser = null;
            let websocket = null;
            
            // Update UI based on auth state
            function updateAuthUI() {
                if (authToken && currentUser) {
                    document.getElementById('auth-section').style.display = 'none';
                    document.getElementById('user-info').style.display = 'block';
                    document.getElementById('user-name').textContent = currentUser.name;
                } else {
                    document.getElementById('auth-section').style.display = 'block';
                    document.getElementById('user-info').style.display = 'none';
                }
            }
            
            function showMessage(message, type = 'info') {
                const div = document.createElement('div');
                div.className = `status ${type}`;
                div.textContent = message;
                document.getElementById('messages').appendChild(div);
                setTimeout(() => div.remove(), 5000);
            }
            
            async function apiCall(endpoint, options = {}) {
                const headers = {
                    'Content-Type': 'application/json',
                    ...(authToken && { 'Authorization': `Bearer ${authToken}` })
                };
                
                const response = await fetch(endpoint, {
                    ...options,
                    headers: { ...headers, ...(options.headers || {}) }
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Request failed');
                }
                
                return response.json();
            }
            
            async function login() {
                try {
                    const email = document.getElementById('email').value;
                    const password = document.getElementById('password').value;
                    
                    const result = await apiCall('/auth/login', {
                        method: 'POST',
                        body: JSON.stringify({ email, password })
                    });
                    
                    authToken = result.token;
                    currentUser = result.user;
                    localStorage.setItem('auth_token', authToken);
                    
                    showMessage('Login successful', 'success');
                    updateAuthUI();
                } catch (error) {
                    showMessage('Login failed: ' + error.message, 'error');
                }
            }
            
            async function register() {
                try {
                    const email = document.getElementById('email').value;
                    const password = document.getElementById('password').value;
                    const name = prompt('Enter your name:');
                    
                    if (!name) return;
                    
                    await apiCall('/auth/register', {
                        method: 'POST',
                        body: JSON.stringify({ email, password, name })
                    });
                    
                    showMessage('Registration successful, please login', 'success');
                } catch (error) {
                    showMessage('Registration failed: ' + error.message, 'error');
                }
            }
            
            async function logout() {
                try {
                    await apiCall('/auth/logout', { method: 'POST' });
                    authToken = null;
                    currentUser = null;
                    localStorage.removeItem('auth_token');
                    
                    showMessage('Logout successful', 'success');
                    updateAuthUI();
                    
                    if (websocket) disconnectWebSocket();
                } catch (error) {
                    showMessage('Logout failed: ' + error.message, 'error');
                }
            }
            
            async function getStats() {
                try {
                    const stats = await apiCall('/stats');
                    document.getElementById('stats-display').innerHTML = 
                        `<pre>${JSON.stringify(stats, null, 2)}</pre>`;
                } catch (error) {
                    showMessage('Failed to get stats: ' + error.message, 'error');
                }
            }
            
            async function getTasks() {
                try {
                    const result = await apiCall('/tasks');
                    document.getElementById('tasks-display').innerHTML = 
                        `<h4>Found ${result.tasks.length} tasks</h4>` +
                        `<pre>${JSON.stringify(result.tasks, null, 2)}</pre>`;
                } catch (error) {
                    showMessage('Failed to get tasks: ' + error.message, 'error');
                }
            }
            
            async function createSampleTask() {
                try {
                    const result = await apiCall('/dev/create-sample-task', { method: 'POST' });
                    showMessage(`Created sample task: ${result.task_id}`, 'success');
                } catch (error) {
                    showMessage('Failed to create sample task: ' + error.message, 'error');
                }
            }
            
            async function createSampleBatch() {
                try {
                    const result = await apiCall('/dev/create-sample-batch', { method: 'POST' });
                    showMessage(`Created ${result.count} sample tasks`, 'success');
                } catch (error) {
                    showMessage('Failed to create sample batch: ' + error.message, 'error');
                }
            }
            
            function connectWebSocket() {
                if (!authToken) {
                    showMessage('Please login first', 'error');
                    return;
                }
                
                const wsUrl = `ws://${window.location.host}/ws?token=${authToken}`;
                websocket = new WebSocket(wsUrl);
                
                websocket.onopen = () => {
                    document.getElementById('ws-status').textContent = 'Connected';
                    document.getElementById('ws-status').className = 'status success';
                    showMessage('WebSocket connected', 'success');
                };
                
                websocket.onmessage = (event) => {
                    const message = JSON.parse(event.data);
                    const div = document.createElement('div');
                    div.textContent = `${new Date().toLocaleTimeString()}: ${JSON.stringify(message)}`;
                    document.getElementById('ws-messages').appendChild(div);
                };
                
                websocket.onclose = () => {
                    document.getElementById('ws-status').textContent = 'Disconnected';
                    document.getElementById('ws-status').className = 'status error';
                    websocket = null;
                };
                
                websocket.onerror = (error) => {
                    showMessage('WebSocket error: ' + error.message, 'error');
                };
            }
            
            function disconnectWebSocket() {
                if (websocket) {
                    websocket.close();
                    websocket = null;
                }
            }
            
            // Initialize
            if (authToken) {
                apiCall('/auth/me').then(result => {
                    currentUser = result.user;
                    updateAuthUI();
                }).catch(() => {
                    authToken = null;
                    localStorage.removeItem('auth_token');
                    updateAuthUI();
                });
            } else {
                updateAuthUI();
            }
            
            // Auto-refresh stats every 30 seconds
            setInterval(() => {
                if (authToken) getStats();
            }, 30000);
        </script>
    </body>
    </html>
    """

# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv('ADMIN_API_PORT', '8002'))
    
    uvicorn.run(
        "admin_api:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Set to True for development
        log_level="info"
    )