"""
Backfin Verification System API
Simple Supabase-only verification system for single verifier
No Redis, no complex queues - just direct database operations
"""
import logging
import sys
import json
import tempfile
import os
from datetime import datetime, timedelta,timezone
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field

# Gemini AI imports
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    types = None

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from config import settings
from database import get_db
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
    require_admin,
    require_admin_or_verifier,
    AuthToken,
    TokenData
)

# Configure logging first
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import AI prompts
try:
    from prompts import category_prompt, headline_prompt, all_prompt, sum_prompt, sentiment_prompt
    PROMPTS_AVAILABLE = True
    logger.info("✅ AI prompts loaded successfully")
except ImportError as e:
    logger.warning(f"⚠️  Could not import AI prompts: {e} - using fallback prompts")
    PROMPTS_AVAILABLE = False
    category_prompt = "Categorize this corporate announcement."
    headline_prompt = "Create a concise headline."
    all_prompt = "Generate a comprehensive summary."
    sum_prompt = "Generate a summary."
    sentiment_prompt = "Analyze sentiment (Positive/Negative/Neutral)."

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# Add CORS middleware
cors_origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Request/Response Models
# ============================================================================

class RegisterRequest(BaseModel):
    """Request model for verifier registration"""
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=2)

class LoginRequest(BaseModel):
    """Request model for verifier login"""
    email: EmailStr
    password: str

class TaskUpdateRequest(BaseModel):
    """Request model for updating task fields"""
    summary: Optional[str] = None
    ai_summary: Optional[str] = None
    category: Optional[str] = None
    headline: Optional[str] = None
    sentiment: Optional[str] = None
    companyname: Optional[str] = None

class VerifyTaskRequest(BaseModel):
    """Request model for verifying a task"""
    notes: Optional[str] = None

class GenerateContentRequest(BaseModel):
    """Request model for generating AI content"""
    fileurl: str
    summary: Optional[str] = None
    ai_summary: Optional[str] = None
    headline: Optional[str] = None
    pages: Optional[str] = Field(default=None, description="Page numbers or ranges to extract (e.g., '1,3-5,7' or '2-4'). If not specified, all pages are used.")
    model: str = Field(default="gemini-2.5-flash-lite", description="Gemini model to use: gemini-2.5-flash-pro or gemini-2.5-flash-lite")

class GenerateContentResponse(BaseModel):
    """Response model for generated AI content"""
    success: bool
    category: str
    headline: str
    ai_summary: str
    sentiment: str
    model_used: str
    error: Optional[str] = None

# ============================================================================
# Gemini Client Initialization
# ============================================================================

gemini_client = None
if GENAI_AVAILABLE and settings.GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("✅ Gemini AI client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
else:
    if not GENAI_AVAILABLE:
        logger.warning("⚠️  Google GenAI not available - content generation disabled")
    if not settings.GEMINI_API_KEY:
        logger.warning("⚠️  GEMINI_API_KEY not configured - content generation disabled")

# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "mode": "production" if settings.PROD else "development"
    }

# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.post(f"{settings.API_PREFIX}/auth/register", response_model=AuthToken)
async def register(request: RegisterRequest, supabase=Depends(get_db)):
    """
    Register a new verifier account
    Note: In production, you might want to restrict this or require admin approval
    """
    try:
        # Check if email already exists
        existing = supabase.table("admin_users").select("email").eq("email", request.email).execute()
        
        if existing.data and len(existing.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        password_hash = get_password_hash(request.password)
        
        # Create user (default role is 'verifier', can be changed to 'admin' manually in DB)
        user_data = {
            "email": request.email,
            "password_hash": password_hash,
            "name": request.name,
            "is_active": True,
            "is_verified": True,  # Auto-verify for simplicity
            "role": "verifier"  # Default role
        }
        
        result = supabase.table("admin_users").insert(user_data).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        user = result.data[0]
        logger.info(f"✅ Registered new user: {user['email']} with role: {user.get('role', 'verifier')}")
        
        # Generate access token with role
        access_token = create_access_token({
            "sub": user["email"], 
            "user_id": user["id"],
            "role": user.get("role", "verifier")
        })
        
        # Create session
        session_data = {
            "user_id": user["id"],
            "session_token": access_token,
            "expires_at": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
            "is_active": True
        }
        
        supabase.table("admin_sessions").insert(session_data).execute()
        
        return AuthToken(
            access_token=access_token,
            token_type="bearer",
            user={
                "id": user["id"],
                "email": user["email"],
                "name": user["name"]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@app.post(f"{settings.API_PREFIX}/auth/login", response_model=AuthToken)
async def login(request: LoginRequest, supabase=Depends(get_db)):
    """
    Login endpoint for verifiers
    Returns JWT token for authentication
    """
    try:
        # Find user by email
        result = supabase.table("admin_users").select("*").eq("email", request.email).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user = result.data[0]
        
        # Check if user is active
        if not user.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )
        
        # Verify password
        if not verify_password(request.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Generate access token with role
        access_token = create_access_token({
            "sub": user["email"], 
            "user_id": user["id"],
            "role": user.get("role", "verifier")
        })
        
        # Invalidate old sessions
        supabase.table("admin_sessions").update({"is_active": False}).eq("user_id", user["id"]).execute()
        
        # Create new session
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=8))
        session_data = {
            "user_id": user["id"],
            "session_token": access_token,
            "expires_at": expires_at.isoformat(),
            "is_active": True
        }
        
        session_result = supabase.table("admin_sessions").insert(session_data).execute()
        logger.info(f"Session created: {len(session_result.data) if session_result.data else 0} records")
        
        # Update last login
        supabase.table("admin_users").update({"updated_at": datetime.utcnow().isoformat()}).eq("id", user["id"]).execute()
        
        logger.info(f"✅ User logged in: {user['email']}")
        
        return AuthToken(
            access_token=access_token,
            token_type="bearer",
            user={
                "id": user["id"],
                "email": user["email"],
                "name": user["name"]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@app.post(f"{settings.API_PREFIX}/auth/logout")
async def logout(current_user: TokenData = Depends(get_current_user), supabase=Depends(get_db)):
    """Logout endpoint - invalidates current session"""
    try:
        # Invalidate all sessions for this user
        supabase.table("admin_sessions").update({"is_active": False}).eq("user_id", current_user.user_id).execute()
        
        logger.info(f"✅ User logged out: {current_user.email}")
        
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@app.get(f"{settings.API_PREFIX}/auth/me")
async def get_current_user_info(current_user: TokenData = Depends(get_current_user), supabase=Depends(get_db)):
    """Get current user information"""
    try:
        result = supabase.table("admin_users").select("id, email, name, created_at").eq("id", current_user.user_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        return result.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user info error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get user info")

# ============================================================================
# Task Management Endpoints
# ============================================================================

@app.get(f"{settings.API_PREFIX}/tasks")
async def get_tasks(
    status_filter: Optional[str] = "queued",
    limit: int = 50,
    current_user: TokenData = Depends(get_current_user),
    supabase=Depends(get_db)
):
    """
    Get list of verification tasks
    Filters: queued, in_progress, verified
    """
    try:
        query = supabase.table("verification_tasks").select("*")
        
        if status_filter:
            query = query.eq("status", status_filter)
        
        query = query.order("created_at", desc=True).limit(limit)
        
        result = query.execute()
        
        return {
            "count": len(result.data) if result.data else 0,
            "tasks": result.data or []
        }
        
    except Exception as e:
        logger.error(f"Get tasks error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch tasks"
        )


@app.post(f"{settings.API_PREFIX}/tasks/claim")
async def claim_task(current_user: TokenData = Depends(get_current_user), supabase=Depends(get_db)):
    """
    Claim the next available queued task
    Uses database function for atomic operation
    """
    try:
        # Get current session
        session_result = supabase.table("admin_sessions").select("id").eq("user_id", current_user.user_id).eq("is_active", True).execute()
        
        if not session_result.data or len(session_result.data) == 0:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No active session")
        
        session_id = session_result.data[0]["id"]
        
        # Call database function to atomically claim a task
        result = supabase.rpc("claim_verification_task", {
            "p_user_id": current_user.user_id,
            "p_session_id": session_id
        }).execute()
        
        if not result.data or len(result.data) == 0:
            return {"message": "No tasks available", "task": None}
        
        task = result.data[0]
        logger.info(f"✅ Task claimed: {task['task_id']} by {current_user.email}")
        
        return {
            "message": "Task claimed successfully",
            "task": task
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Claim task error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to claim task: {str(e)}"
        )


@app.get(f"{settings.API_PREFIX}/tasks/{{task_id}}")
async def get_task(task_id: str, current_user: TokenData = Depends(get_current_user), supabase=Depends(get_db)):
    """Get detailed information about a specific task"""
    try:
        result = supabase.table("verification_tasks").select("*").eq("id", task_id).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        
        task = result.data[0]
        
        # Get edit history
        edits = supabase.table("verification_edits").select("*").eq("task_id", task_id).order("edited_at", desc=True).execute()
        
        return {
            "task": task,
            "edit_history": edits.data or []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get task error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get task")


@app.patch(f"{settings.API_PREFIX}/tasks/{{task_id}}")
async def update_task(
    task_id: str,
    updates: TaskUpdateRequest,
    current_user: TokenData = Depends(get_current_user),
    supabase=Depends(get_db)
):
    """
    Update task fields (edit announcement data)
    Tracks all changes in verification_edits table
    """
    try:
        # Get current task
        task_result = supabase.table("verification_tasks").select("*").eq("id", task_id).execute()
        
        if not task_result.data or len(task_result.data) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        
        task = task_result.data[0]
        
        # Check if task is in editable state
        if task["status"] not in ["queued", "in_progress"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task cannot be edited in current status"
            )
        
        # Get current data
        current_data = task.get("current_data", {})
        original_data = task.get("original_data", {})
        
        # Track changes
        changes_made = []
        updated_data = current_data.copy()
        
        # Apply updates and track changes
        update_fields = updates.dict(exclude_unset=True)
        for field, new_value in update_fields.items():
            if new_value is not None:
                old_value = current_data.get(field)
                if old_value != new_value:
                    updated_data[field] = new_value
                    changes_made.append({
                        "field_name": field,
                        "original_value": str(old_value) if old_value else None,
                        "current_value": str(new_value),
                        "task_id": task_id,
                        "edited_by": current_user.user_id
                    })
        
        if not changes_made:
            return {"message": "No changes made", "task": task}
        
        # Update task
        update_payload = {
            "current_data": updated_data,
            "has_edits": True,
            "edit_count": task.get("edit_count", 0) + len(changes_made),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        updated_task = supabase.table("verification_tasks").update(update_payload).eq("id", task_id).execute()
        
        # Record edits
        if changes_made:
            supabase.table("verification_edits").insert(changes_made).execute()
        
        logger.info(f"✅ Task updated: {task_id}, {len(changes_made)} changes by {current_user.email}")
        
        return {
            "message": "Task updated successfully",
            "changes_count": len(changes_made),
            "task": updated_task.data[0] if updated_task.data else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update task error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update task: {str(e)}"
        )


@app.post(f"{settings.API_PREFIX}/tasks/{{task_id}}/verify")
async def verify_task(
    task_id: str,
    request: VerifyTaskRequest,
    current_user: TokenData = Depends(get_current_user),
    supabase=Depends(get_db)
):
    """
    Verify and publish a task
    Copies data from verification_tasks to corporatefilings and marks as verified
    """
    try:
        # Call database function to verify and publish
        result = supabase.rpc("verify_and_publish_task", {
            "p_task_id": task_id,
            "p_user_id": current_user.user_id,
            "p_notes": request.notes
        }).execute()
        
        if result.data is True:
            logger.info(f"✅ Task verified: {task_id} by {current_user.email}")
            return {"message": "Task verified and published successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Verification failed"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify task error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify task: {str(e)}"
        )


@app.post(f"{settings.API_PREFIX}/tasks/{{task_id}}/release")
async def release_task(
    task_id: str,
    current_user: TokenData = Depends(get_current_user),
    supabase=Depends(get_db)
):
    """
    Release a task back to queue (if verifier can't complete it)
    """
    try:
        # Get task
        task_result = supabase.table("verification_tasks").select("*").eq("id", task_id).execute()
        
        if not task_result.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        
        task = task_result.data[0]
        
        # Check if user owns the task
        if task["assigned_to_user"] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only release tasks assigned to you"
            )
        
        # Release task
        supabase.table("verification_tasks").update({
            "status": "queued",
            "assigned_to_user": None,
            "assigned_to_session": None,
            "assigned_at": None,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", task_id).execute()
        
        logger.info(f"✅ Task released: {task_id} by {current_user.email}")
        
        return {"message": "Task released successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Release task error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to release task"
        )


# ============================================================================
# Direct Corporate Filings Endpoints (Simplified Approach)
# ============================================================================

@app.get(f"{settings.API_PREFIX}/announcements")
async def get_unverified_announcements(
    verified: bool = False,
    page: int = 1,
    page_size: int = 50,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    supabase=Depends(get_db)
):
    """Get announcements with pagination, date filters, and optional category filter"""
    try:
        # Validate pagination parameters
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50
        elif page_size > 100:
            page_size = 100
            
        offset = (page - 1) * page_size
        
        logger.info(f"Fetching announcements: verified={verified}, page={page}, page_size={page_size}, start_date={start_date}, end_date={end_date}, category={category}")
        
        # Build query
        query = supabase.table("corporatefilings").select("*", count="exact").eq("verified", verified)
        
        # Apply category filter if specified
        if category:
            query = query.eq("category", category)
        
        # Apply date filters
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                start_iso = start_dt.isoformat()
                query = query.gte('date', start_iso)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use YYYY-MM-DD"
                )
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                end_iso = end_dt.isoformat()
                query = query.lte('date', end_iso)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use YYYY-MM-DD"
                )
        
        # Apply pagination and ordering
        query = query.order("date", desc=True).range(offset, offset + page_size - 1)
        
        result = query.execute()
        
        total_count = result.count if hasattr(result, 'count') else 0
        total_pages = (total_count + page_size - 1) // page_size if total_count else 0
        
        logger.info(f"Found {len(result.data)} announcements (page {page}/{total_pages}, total: {total_count})")
        
        return {
            "announcements": result.data,
            "count": len(result.data),
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "has_next": page < total_pages,
            "has_previous": page > 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get announcements error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch announcements: {str(e)}"
        )


@app.get(f"{settings.API_PREFIX}/announcements/financial-results")
async def get_financial_results(
    verified: bool = False,
    page: int = 1,
    page_size: int = 50,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    supabase=Depends(get_db)
):
    """Get Financial Results announcements only (category parameter is ignored for this endpoint)"""
    try:
        # Validate pagination parameters
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50
        elif page_size > 100:
            page_size = 100
            
        offset = (page - 1) * page_size
        
        logger.info(f"Fetching Financial Results: verified={verified}, page={page}, page_size={page_size}")
        
        # Build query with category filter
        query = supabase.table("corporatefilings").select("*", count="exact")\
            .eq("verified", verified)\
            .eq("category", "Financial Results")
        
        # Apply date filters
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                start_iso = start_dt.isoformat()
                query = query.gte('date', start_iso)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use YYYY-MM-DD"
                )
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                end_iso = end_dt.isoformat()
                query = query.lte('date', end_iso)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use YYYY-MM-DD"
                )
        
        # Apply pagination and ordering
        query = query.order("date", desc=True).range(offset, offset + page_size - 1)
        
        result = query.execute()
        
        total_count = result.count if hasattr(result, 'count') else 0
        total_pages = (total_count + page_size - 1) // page_size if total_count else 0
        
        logger.info(f"Found {len(result.data)} Financial Results (page {page}/{total_pages}, total: {total_count})")
        
        return {
            "announcements": result.data,
            "count": len(result.data),
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "has_next": page < total_pages,
            "has_previous": page > 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get financial results error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch financial results: {str(e)}"
        )


@app.get(f"{settings.API_PREFIX}/announcements/non-financial")
async def get_non_financial_results(
    verified: bool = False,
    page: int = 1,
    page_size: int = 50,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    supabase=Depends(get_db)
):
    """Get all announcements except Financial Results (category parameter is ignored for this endpoint)"""
    try:
        # Validate pagination parameters
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50
        elif page_size > 100:
            page_size = 100
            
        offset = (page - 1) * page_size
        
        logger.info(f"Fetching non-Financial Results: verified={verified}, page={page}, page_size={page_size}")
        
        # Build query excluding Financial Results
        query = supabase.table("corporatefilings").select("*", count="exact")\
            .eq("verified", verified)\
            .neq("category", "Financial Results")
        
        # Apply date filters
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                start_iso = start_dt.isoformat()
                query = query.gte('date', start_iso)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use YYYY-MM-DD"
                )
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                end_iso = end_dt.isoformat()
                query = query.lte('date', end_iso)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use YYYY-MM-DD"
                )
        
        # Apply pagination and ordering
        query = query.order("date", desc=True).range(offset, offset + page_size - 1)
        
        result = query.execute()
        
        total_count = result.count if hasattr(result, 'count') else 0
        total_pages = (total_count + page_size - 1) // page_size if total_count else 0
        
        logger.info(f"Found {len(result.data)} non-Financial Results (page {page}/{total_pages}, total: {total_count})")
        
        return {
            "announcements": result.data,
            "count": len(result.data),
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "has_next": page < total_pages,
            "has_previous": page > 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get non-financial results error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch non-financial results: {str(e)}"
        )


@app.get(f"{settings.API_PREFIX}/announcements/{{corp_id}}")
async def get_announcement(
    corp_id: str,
    current_user: TokenData = Depends(get_current_user),
    supabase=Depends(get_db)
):
    """Get a specific announcement by corp_id"""
    try:
        result = supabase.table("corporatefilings")\
            .select("*")\
            .eq("corp_id", corp_id)\
            .single()\
            .execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Announcement with corp_id {corp_id} not found"
            )
        
        return result.data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get announcement error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch announcement: {str(e)}"
        )


class AnnouncementUpdate(BaseModel):
    """Model for updating announcement fields"""
    announcement: Optional[str] = None
    description: Optional[str] = None
    summary: Optional[str] = None
    symbol: Optional[str] = None
    company: Optional[str] = None
    companyname: Optional[str] = None
    headline: Optional[str] = None
    category: Optional[str] = None
    ai_summary: Optional[str] = None
    # Add other fields as needed


@app.patch(f"{settings.API_PREFIX}/announcements/{{corp_id}}")
async def update_announcement(
    corp_id: str,
    update: AnnouncementUpdate,
    current_user: TokenData = Depends(get_current_user),
    supabase=Depends(get_db)
):
    """Update announcement content (without marking as verified)"""
    try:
        # Build update dict excluding None values
        update_data = {k: v for k, v in update.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        logger.info(f"Updating announcement {corp_id}: {update_data}")
        
        result = supabase.table("corporatefilings")\
            .update(update_data)\
            .eq("corp_id", corp_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Announcement with corp_id {corp_id} not found"
            )
        
        return {
            "success": True,
            "corp_id": corp_id,
            "updated": result.data[0]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update announcement error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update announcement: {str(e)}"
        )


class VerifyRequest(BaseModel):
    """Model for verification request"""
    notes: Optional[str] = None


@app.post(f"{settings.API_PREFIX}/announcements/{{corp_id}}/verify")
async def verify_announcement(
    corp_id: str,
    verify_req: VerifyRequest = None,
    current_user: TokenData = Depends(get_current_user),
    supabase=Depends(get_db)
):
    """Mark announcement as verified"""
    try:
        logger.info(f"Verifying announcement {corp_id} by user {current_user.user_id}")
        
        result = supabase.table("corporatefilings")\
            .update({
                "verified": True,
                "verified_at": datetime.utcnow().isoformat(),
                "verified_by": current_user.user_id
            })\
            .eq("corp_id", corp_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Announcement with corp_id {corp_id} not found"
            )
        
        logger.info(f"✅ Successfully verified announcement {corp_id}")
        
        return {
            "success": True,
            "corp_id": corp_id,
            "verified_at": result.data[0]["verified_at"],
            "verified_by": current_user.user_id,
            "message": "Announcement verified successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify announcement error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify announcement: {str(e)}"
        )


@app.post(f"{settings.API_PREFIX}/announcements/{{corp_id}}/unverify")
async def unverify_announcement(
    corp_id: str,
    current_user: TokenData = Depends(get_current_user),
    supabase=Depends(get_db)
):
    """Mark announcement as unverified (for corrections)"""
    try:
        logger.info(f"Unmarking verification for {corp_id}")
        
        result = supabase.table("corporatefilings")\
            .update({
                "verified": False,
                "verified_at": None,
                "verified_by": None,
                "review_status": None,
                "sent_to_review_at": None,
                "sent_to_review_by": None,
                "review_notes": None
            })\
            .eq("corp_id", corp_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Announcement with corp_id {corp_id} not found"
            )
        
        return {
            "success": True,
            "corp_id": corp_id,
            "message": "Verification removed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unverify announcement error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unverify announcement: {str(e)}"
        )


# ============================================================================
# Review Queue Endpoints (Admin Only)
# ============================================================================

class SendToReviewRequest(BaseModel):
    """Request model for sending announcement to review"""
    notes: Optional[str] = None


@app.post(f"{settings.API_PREFIX}/announcements/{{corp_id}}/send-to-review")
async def send_to_review(
    corp_id: str,
    request: SendToReviewRequest = None,
    current_user: TokenData = Depends(require_admin),
    supabase=Depends(get_db)
):
    """
    Send a verified announcement to review queue (Admin only)
    This allows admins to flag verified announcements that need additional review
    """
    try:
        logger.info(f"Admin {current_user.email} sending announcement {corp_id} to review")
        
        # Check if announcement exists and is verified
        check_result = supabase.table("corporatefilings")\
            .select("corp_id, verified, review_status")\
            .eq("corp_id", corp_id)\
            .execute()
        
        if not check_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Announcement with corp_id {corp_id} not found"
            )
        
        announcement = check_result.data[0]
        
        if not announcement.get("verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only verified announcements can be sent to review"
            )
        
        # Update announcement to pending review status
        notes = request.notes if request else None
        result = supabase.table("corporatefilings")\
            .update({
                "review_status": "pending_review",
                "sent_to_review_at": datetime.utcnow().isoformat(),
                "sent_to_review_by": current_user.user_id,
                "review_notes": notes
            })\
            .eq("corp_id", corp_id)\
            .execute()
        
        logger.info(f"✅ Announcement {corp_id} sent to review queue")
        
        return {
            "success": True,
            "corp_id": corp_id,
            "review_status": "pending_review",
            "sent_to_review_at": result.data[0]["sent_to_review_at"],
            "sent_to_review_by": current_user.user_id,
            "message": "Announcement sent to review queue successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send to review error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send announcement to review: {str(e)}"
        )


@app.get(f"{settings.API_PREFIX}/review-queue")
async def get_review_queue(
    page: int = 1,
    page_size: int = 50,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    current_user: TokenData = Depends(require_admin),
    supabase=Depends(get_db)
):
    """
    Get announcements in review queue (Admin only)
    Returns verified announcements that have been flagged for review
    """
    try:
        # Validate pagination
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50
        elif page_size > 100:
            page_size = 100
            
        offset = (page - 1) * page_size
        
        logger.info(f"Admin {current_user.email} fetching review queue: page={page}, page_size={page_size}")
        
        # Build query for pending review items
        query = supabase.table("corporatefilings")\
            .select("*", count="exact")\
            .eq("verified", True)\
            .eq("review_status", "pending_review")
        
        # Apply category filter if specified
        if category:
            query = query.eq("category", category)
        
        # Apply date filters
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                start_iso = start_dt.isoformat()
                query = query.gte('date', start_iso)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use YYYY-MM-DD"
                )
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                end_iso = end_dt.isoformat()
                query = query.lte('date', end_iso)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use YYYY-MM-DD"
                )
        
        # Apply ordering and pagination
        query = query.order("sent_to_review_at", desc=True).range(offset, offset + page_size - 1)
        
        result = query.execute()
        
        total_count = result.count if hasattr(result, 'count') else 0
        total_pages = (total_count + page_size - 1) // page_size if total_count else 0
        
        logger.info(f"Found {len(result.data)} announcements in review queue (page {page}/{total_pages}, total: {total_count})")
        
        return {
            "announcements": result.data,
            "count": len(result.data),
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "has_next": page < total_pages,
            "has_previous": page > 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get review queue error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch review queue: {str(e)}"
        )


class ReviewDecisionRequest(BaseModel):
    """Request model for review decision"""
    action: str = Field(..., description="'approve' or 'reject'")
    notes: Optional[str] = None


@app.post(f"{settings.API_PREFIX}/announcements/{{corp_id}}/review")
async def review_announcement(
    corp_id: str,
    request: ReviewDecisionRequest,
    current_user: TokenData = Depends(require_admin),
    supabase=Depends(get_db)
):
    """
    Make a review decision on an announcement (Admin only)
    - approve: Marks as approved and keeps verified status
    - reject: Sends back to verification queue (unverified)
    """
    try:
        if request.action not in ["approve", "reject"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action must be either 'approve' or 'reject'"
            )
        
        logger.info(f"Admin {current_user.email} reviewing announcement {corp_id}: action={request.action}")
        
        # Check if announcement is in review queue
        check_result = supabase.table("corporatefilings")\
            .select("corp_id, verified, review_status")\
            .eq("corp_id", corp_id)\
            .execute()
        
        if not check_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Announcement with corp_id {corp_id} not found"
            )
        
        announcement = check_result.data[0]
        
        if announcement.get("review_status") != "pending_review":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Announcement is not in review queue"
            )
        
        # Update based on action
        if request.action == "approve":
            update_data = {
                "review_status": "approved",
                "reviewed_at": datetime.utcnow().isoformat(),
                "reviewed_by": current_user.user_id,
                "review_notes": request.notes
            }
            message = "Announcement approved successfully"
        else:  # reject
            update_data = {
                "verified": False,
                "verified_at": None,
                "verified_by": None,
                "review_status": "rejected",
                "reviewed_at": datetime.utcnow().isoformat(),
                "reviewed_by": current_user.user_id,
                "review_notes": request.notes
            }
            message = "Announcement rejected and sent back to verification queue"
        
        result = supabase.table("corporatefilings")\
            .update(update_data)\
            .eq("corp_id", corp_id)\
            .execute()
        
        logger.info(f"✅ Announcement {corp_id} {request.action}ed by admin {current_user.email}")
        
        return {
            "success": True,
            "corp_id": corp_id,
            "action": request.action,
            "review_status": update_data["review_status"],
            "reviewed_at": update_data["reviewed_at"],
            "reviewed_by": current_user.user_id,
            "message": message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Review announcement error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to review announcement: {str(e)}"
        )


# ============================================================================
# Statistics Endpoints
# ============================================================================

@app.get(f"{settings.API_PREFIX}/stats")
async def get_stats(current_user: TokenData = Depends(get_current_user), supabase=Depends(get_db)):
    """Get verification statistics including review queue (admin sees review stats)"""
    try:
        # Count by verification status
        unverified = supabase.table("corporatefilings").select("corp_id", count="exact").eq("verified", False).execute()
        verified = supabase.table("corporatefilings").select("corp_id", count="exact").eq("verified", True).execute()
        
        # Count verified today
        today = datetime.utcnow().date().isoformat()
        verified_today = supabase.table("corporatefilings").select("corp_id", count="exact").eq("verified", True).gte("verified_at", today).execute()
        
        stats = {
            "unverified": unverified.count or 0,
            "verified_total": verified.count or 0,
            "verified_today": verified_today.count or 0,
            "user_role": current_user.role
        }
        
        # Add review queue stats for admins only
        if current_user.role == "admin":
            pending_review = supabase.table("corporatefilings")\
                .select("corp_id", count="exact")\
                .eq("verified", True)\
                .eq("review_status", "pending_review")\
                .execute()
            
            approved = supabase.table("corporatefilings")\
                .select("corp_id", count="exact")\
                .eq("review_status", "approved")\
                .execute()
            
            rejected = supabase.table("corporatefilings")\
                .select("corp_id", count="exact")\
                .eq("review_status", "rejected")\
                .execute()
            
            stats["review_queue"] = {
                "pending_review": pending_review.count or 0,
                "approved": approved.count or 0,
                "rejected": rejected.count or 0
            }
        
        return stats
        
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get statistics"
        )


# ============================================================================
# Company Changes Verification Endpoints
# ============================================================================

class CompanyChangeVerifyRequest(BaseModel):
    """Request model for verifying company change"""
    notes: Optional[str] = None


class CompanyChangeReviewRequest(BaseModel):
    """Request model for reviewing company change"""
    action: str = Field(..., description="'approve' or 'reject'")
    notes: Optional[str] = None


@app.get(f"{settings.API_PREFIX}/company-changes/pending")
async def get_pending_company_changes(
    page: int = 1,
    page_size: int = 50,
    change_type: Optional[str] = None,
    is_new_company: Optional[bool] = None,
    current_user: TokenData = Depends(require_admin_or_verifier),
    supabase=Depends(get_db)
):
    """
    Get pending company changes awaiting verification
    Accessible by both admins and verifiers
    """
    try:
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50
        elif page_size > 100:
            page_size = 100
            
        offset = (page - 1) * page_size
        
        logger.info(f"User {current_user.email} fetching pending company changes: page={page}")
        
        # Build query
        query = supabase.table("company_changes_pending")\
            .select("*", count="exact")\
            .eq("verified", False)\
            .eq("applied", False)
        
        # Apply filters
        if change_type:
            query = query.eq("change_type", change_type)
        
        if is_new_company is not None:
            if is_new_company:
                query = query.is_("company_id", "null")
            else:
                query = query.not_.is_("company_id", "null")
        
        # Apply ordering and pagination
        query = query.order("detected_at", desc=True).range(offset, offset + page_size - 1)
        
        result = query.execute()
        
        total_count = result.count if hasattr(result, 'count') else 0
        total_pages = (total_count + page_size - 1) // page_size if total_count else 0
        
        logger.info(f"Found {len(result.data)} pending company changes")
        
        return {
            "changes": result.data,
            "count": len(result.data),
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "has_next": page < total_pages,
            "has_previous": page > 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get pending company changes error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending changes: {str(e)}"
        )


@app.get(f"{settings.API_PREFIX}/company-changes/stats")
async def get_company_changes_stats(
    current_user: TokenData = Depends(require_admin_or_verifier),
    supabase=Depends(get_db)
):
    """Get statistics about company changes"""
    try:
        result = supabase.table("company_changes_stats").select("*").execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        else:
            return {
                "pending_verification": 0,
                "ready_to_apply": 0,
                "applied": 0,
                "rejected": 0,
                "new_companies": 0,
                "isin_changes": 0,
                "name_changes": 0,
                "code_changes": 0
            }
        
    except Exception as e:
        logger.error(f"Get company changes stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get company changes statistics"
        )


@app.get(f"{settings.API_PREFIX}/company-changes/{{change_id}}")
async def get_company_change_detail(
    change_id: str,
    current_user: TokenData = Depends(require_admin_or_verifier),
    supabase=Depends(get_db)
):
    """Get detailed information about a specific company change"""
    try:
        result = supabase.table("company_changes_pending")\
            .select("*")\
            .eq("id", change_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company change with ID {change_id} not found"
            )
        
        # Get audit log for this change
        audit_result = supabase.table("company_changes_audit_log")\
            .select("*")\
            .eq("pending_change_id", change_id)\
            .order("created_at", desc=False)\
            .execute()
        
        change_data = result.data[0]
        change_data['audit_log'] = audit_result.data
        
        return change_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get company change detail error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch change details: {str(e)}"
        )


@app.post(f"{settings.API_PREFIX}/company-changes/{{change_id}}/verify")
async def verify_company_change(
    change_id: str,
    request: CompanyChangeVerifyRequest = None,
    current_user: TokenData = Depends(require_admin_or_verifier),
    supabase=Depends(get_db)
):
    """Mark a company change as verified"""
    try:
        logger.info(f"User {current_user.email} verifying company change {change_id}")
        
        # Check if change exists and is not already verified
        check_result = supabase.table("company_changes_pending")\
            .select("id, verified, applied, isin, change_type")\
            .eq("id", change_id)\
            .execute()
        
        if not check_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company change with ID {change_id} not found"
            )
        
        change = check_result.data[0]
        
        if change.get("verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This change has already been verified"
            )
        
        if change.get("applied"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This change has already been applied"
            )
        
        # Update verification status
        notes = request.notes if request else None
        result = supabase.table("company_changes_pending")\
            .update({
                "verified": True,
                "verified_at": datetime.utcnow().isoformat(),
                "verified_by": current_user.user_id,
                "review_status": "approved",
                "review_notes": notes,
                "updated_at": datetime.utcnow().isoformat()
            })\
            .eq("id", change_id)\
            .execute()
        
        logger.info(f"✅ Company change {change_id} verified by {current_user.email}")
        
        return {
            "success": True,
            "change_id": change_id,
            "isin": change.get("isin"),
            "change_type": change.get("change_type"),
            "verified_at": result.data[0]["verified_at"],
            "verified_by": current_user.user_id,
            "message": "Company change verified successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify company change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify change: {str(e)}"
        )


@app.post(f"{settings.API_PREFIX}/company-changes/{{change_id}}/reject")
async def reject_company_change(
    change_id: str,
    request: CompanyChangeReviewRequest,
    current_user: TokenData = Depends(require_admin_or_verifier),
    supabase=Depends(get_db)
):
    """Reject a company change"""
    try:
        logger.info(f"User {current_user.email} rejecting company change {change_id}")
        
        result = supabase.table("company_changes_pending")\
            .update({
                "review_status": "rejected",
                "reviewed_at": datetime.utcnow().isoformat(),
                "reviewed_by": current_user.user_id,
                "review_notes": request.notes,
                "updated_at": datetime.utcnow().isoformat()
            })\
            .eq("id", change_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company change with ID {change_id} not found"
            )
        
        logger.info(f"✅ Company change {change_id} rejected by {current_user.email}")
        
        return {
            "success": True,
            "change_id": change_id,
            "review_status": "rejected",
            "reviewed_at": result.data[0]["reviewed_at"],
            "reviewed_by": current_user.user_id,
            "message": "Company change rejected successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reject company change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject change: {str(e)}"
        )


@app.post(f"{settings.API_PREFIX}/company-changes/apply-verified")
async def apply_verified_company_changes(
    current_user: TokenData = Depends(require_admin),
    supabase=Depends(get_db)
):
    """
    Apply all verified company changes to stocklistdata table (Admin only)
    This bulk operation applies all approved changes
    """
    try:
        logger.info(f"Admin {current_user.email} applying verified company changes")
        
        # Get all verified and approved changes that haven't been applied
        result = supabase.table("company_changes_pending")\
            .select("id, isin, change_type")\
            .eq("verified", True)\
            .eq("applied", False)\
            .eq("review_status", "approved")\
            .execute()
        
        if not result.data or len(result.data) == 0:
            return {
                "success": True,
                "applied_count": 0,
                "message": "No verified changes to apply"
            }
        
        changes_to_apply = result.data
        applied_count = 0
        errors = []
        
        for change in changes_to_apply:
            try:
                # Call the database function to apply the change
                apply_result = supabase.rpc(
                    'apply_company_change',
                    {
                        'change_id': change['id'],
                        'applied_by_user': current_user.user_id
                    }
                ).execute()
                
                if apply_result.data and apply_result.data.get('success'):
                    applied_count += 1
                    logger.info(f"✅ Applied change {change['id']} for ISIN {change['isin']}")
                else:
                    error_msg = apply_result.data.get('error', 'Unknown error')
                    errors.append(f"ISIN {change['isin']}: {error_msg}")
                    logger.error(f"❌ Failed to apply change {change['id']}: {error_msg}")
                    
            except Exception as e:
                errors.append(f"ISIN {change['isin']}: {str(e)}")
                logger.error(f"❌ Error applying change {change['id']}: {str(e)}")
        
        logger.info(f"✅ Applied {applied_count}/{len(changes_to_apply)} company changes")
        
        return {
            "success": True,
            "total_changes": len(changes_to_apply),
            "applied_count": applied_count,
            "error_count": len(errors),
            "errors": errors if errors else None,
            "message": f"Successfully applied {applied_count} company changes to stocklistdata"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Apply verified changes error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply changes: {str(e)}"
        )


# ============================================================================
# AI Content Generation
# ============================================================================

def parse_page_specification(page_spec: str) -> List[int]:
    """
    Parse page specification string into list of page numbers.
    Supports formats like: "1", "1,3,5", "2-4", "1,3-5,7-9"
    
    Args:
        page_spec: String specifying pages (e.g., "1,3-5,7")
        
    Returns:
        Sorted list of unique page numbers (0-indexed)
    """
    if not page_spec or not page_spec.strip():
        return []
    
    pages = set()
    parts = page_spec.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            # Range specification
            try:
                start, end = part.split('-', 1)
                start = int(start.strip())
                end = int(end.strip())
                if start < 1 or end < 1:
                    raise ValueError("Page numbers must be positive")
                if start > end:
                    raise ValueError(f"Invalid range: {start}-{end}")
                # Convert to 0-indexed
                pages.update(range(start - 1, end))
            except ValueError as e:
                raise ValueError(f"Invalid page range '{part}': {str(e)}")
        else:
            # Single page
            try:
                page_num = int(part)
                if page_num < 1:
                    raise ValueError("Page numbers must be positive")
                pages.add(page_num - 1)  # Convert to 0-indexed
            except ValueError:
                raise ValueError(f"Invalid page number '{part}'")
    
    return sorted(list(pages))


def extract_pdf_pages(input_path: str, output_path: str, page_numbers: List[int]) -> int:
    """
    Extract specific pages from a PDF and save to a new file.
    
    Args:
        input_path: Path to input PDF
        output_path: Path to save extracted pages
        page_numbers: List of 0-indexed page numbers to extract
        
    Returns:
        Number of pages extracted
    """
    try:
        from PyPDF2 import PdfReader, PdfWriter
    except ImportError:
        raise ImportError("PyPDF2 is required for page extraction. Install with: pip install PyPDF2")
    
    reader = PdfReader(input_path)
    total_pages = len(reader.pages)
    
    # Validate page numbers
    invalid_pages = [p for p in page_numbers if p >= total_pages]
    if invalid_pages:
        raise ValueError(f"Page numbers {[p+1 for p in invalid_pages]} exceed document length ({total_pages} pages)")
    
    writer = PdfWriter()
    
    for page_num in page_numbers:
        writer.add_page(reader.pages[page_num])
    
    with open(output_path, 'wb') as output_file:
        writer.write(output_file)
    
    return len(page_numbers)


@app.post(f"{settings.API_PREFIX}/generate-content", response_model=GenerateContentResponse)
async def generate_content(
    request: GenerateContentRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Generate AI content from announcement PDF using Gemini
    
    Args:
        request: Contains fileurl, summary, and model selection
        current_user: Authenticated admin user
        
    Returns:
        Generated category, headline, AI summary, financial data, and sentiment
    """
    if not GENAI_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI content generation not available - Google GenAI library not installed"
        )
    
    if not gemini_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI content generation not available - Gemini API key not configured"
        )
    
    # Validate model selection
    valid_models = ["gemini-2.5-pro", "gemini-2.5-flash-lite"]
    model_to_use = request.model if request.model in valid_models else "gemini-2.5-flash-lite"
    
    logger.info(f"🤖 Generating content for PDF: {request.fileurl} using model: {model_to_use}")
    
    # Build comprehensive prompt using imported prompts
    base_instruction = """Analyze the provided announcement document and extract the following information following the detailed guidelines below:"""
    
    prompt_sections = [
        base_instruction,
        "",
        "1. CATEGORY ANALYSIS:",
        category_prompt,
        "",
        "2. HEADLINE CREATION:",
        headline_prompt,
        "",
        "3. SUMMARY GENERATION:",
        all_prompt,
        "",
        "4. SENTIMENT ANALYSIS:",
        sentiment_prompt,
        "",
        "Return the response as a structured JSON with fields: category, headline, ai_summary, sentiment"
    ]
    
    # Add context if provided
    context_parts = []
    if request.summary:
        context_parts.append(f"**Original Summary for Context:** {request.summary}")
    if request.ai_summary:
        context_parts.append(f"**Previous AI Summary for Reference:** {request.ai_summary}")
    if request.headline:
        context_parts.append(f"**Previous Headline for Reference:** {request.headline}")
    
    if context_parts:
        prompt = "\n\n".join([
            "=== CONTEXT FROM PREVIOUS ANALYSIS ===",
            *context_parts,
            "",
            "=== ANALYSIS INSTRUCTIONS ===",
            *prompt_sections
        ])
    else:
        prompt = "\n".join(prompt_sections)
    
    temp_file_path = None
    uploaded_file = None
    
    try:
        # Download PDF from URL
        import requests
        logger.info(f"📥 Downloading PDF from {request.fileurl}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/pdf,application/x-pdf,*/*',
            'Referer': 'https://www.bseindia.com/'
        }
        response = requests.get(request.fileurl, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name
        
        logger.info(f"💾 Saved PDF to {temp_file_path}")
        
        # Extract specific pages if requested
        file_to_upload = temp_file_path
        extracted_file_path = None
        
        if request.pages:
            try:
                logger.info(f"📄 Extracting pages: {request.pages}")
                page_numbers = parse_page_specification(request.pages)
                
                if page_numbers:
                    # Create another temp file for extracted pages
                    with tempfile.NamedTemporaryFile(delete=False, suffix='_extracted.pdf') as extracted_file:
                        extracted_file_path = extracted_file.name
                    
                    num_pages = extract_pdf_pages(temp_file_path, extracted_file_path, page_numbers)
                    logger.info(f"✅ Extracted {num_pages} pages: {[p+1 for p in page_numbers]}")
                    file_to_upload = extracted_file_path
                else:
                    logger.warning("No valid pages specified, using full PDF")
            except ValueError as e:
                logger.error(f"Page extraction error: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid page specification: {str(e)}"
                )
            except ImportError as e:
                logger.error(f"PyPDF2 not available: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="PDF page extraction not available. PyPDF2 library required."
                )
            except Exception as e:
                logger.error(f"Failed to extract pages: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to extract pages: {str(e)}"
                )
        
        # Upload to Gemini
        logger.info(f"📤 Uploading PDF to Gemini")
        uploaded_file = gemini_client.files.upload(file=file_to_upload)
        
        # Define response schema
        class AIOutput(BaseModel):
            category: str = Field(description="The most specific category")
            headline: str = Field(description="Concise informative headline")
            ai_summary: str = Field(description="Comprehensive narrative report")
            sentiment: str = Field(description="Market sentiment (Positive, Negative, or Neutral)")
        
        # Generate content
        logger.info(f"🤖 Generating AI content with {model_to_use}")
        ai_response = gemini_client.models.generate_content(
            model=model_to_use,
            contents=[prompt, uploaded_file],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AIOutput,
                thinking_config=types.ThinkingConfig(thinking_budget=-1) if model_to_use == "gemini-2.0-flash-pro" else None
            )
        )
        
        # Parse response
        logger.info("📝 Parsing AI response")
        result_data = json.loads(ai_response.text.strip())
        
        if isinstance(result_data, list) and len(result_data) > 0:
            result_data = result_data[0]
        
        category = result_data.get("category", "Procedural/Administrative")
        headline = result_data.get("headline", "")
        ai_summary = result_data.get("ai_summary", "")
        sentiment = result_data.get("sentiment", "Neutral")
        
        logger.info(f"✅ AI content generated successfully - Category: {category}")
        
        # Cleanup uploaded file
        try:
            gemini_client.files.delete(name=uploaded_file.name)
        except Exception as e:
            logger.warning(f"Failed to delete uploaded file: {e}")
        
        return GenerateContentResponse(
            success=True,
            category=category,
            headline=headline,
            ai_summary=ai_summary,
            sentiment=sentiment,
            model_used=model_to_use
        )
        
    except requests.RequestException as e:
        logger.error(f"Failed to download PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to download PDF from URL: {str(e)}"
        )
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse AI response"
        )
    except Exception as e:
        logger.error(f"Content generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Content generation failed: {str(e)}"
        )
    finally:
        # Cleanup temporary files
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.info(f"🗑️  Cleaned up temporary file")
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")
        
        if extracted_file_path and os.path.exists(extracted_file_path):
            try:
                os.unlink(extracted_file_path)
                logger.info(f"🗑️  Cleaned up extracted pages file")
            except Exception as e:
                logger.warning(f"Failed to delete extracted file: {e}")


# ============================================================================
# Deals Verification Endpoints
# ============================================================================

class DealUpdateRequest(BaseModel):
    """Request model for updating deal fields"""
    symbol: Optional[str] = None
    securityid: Optional[str] = None
    date: Optional[str] = None
    client_name: Optional[str] = None
    deal_type: Optional[str] = None
    quantity: Optional[int] = None
    price: Optional[str] = None
    exchange: Optional[str] = None
    deal: Optional[str] = None

class DealVerifyRequest(BaseModel):
    """Request model for verifying a deal"""
    notes: Optional[str] = None

class DealRejectRequest(BaseModel):
    """Request model for rejecting a deal"""
    reason: str = Field(min_length=5, description="Reason for rejection")


# ============================================================================
# Stock Price Data Refresh Endpoint
# ============================================================================

class RefreshStockPriceRequest(BaseModel):
    """Request model for refreshing stock price data"""
    securityid: int = Field(..., description="Security ID to refresh data for")


class RefreshStockPriceResponse(BaseModel):
    """Response model for stock price refresh"""
    success: bool
    securityid: int
    symbol: Optional[str] = None
    isin: Optional[str] = None
    exchange: Optional[str] = None
    records_fetched: Optional[int] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    message: str
    error: Optional[str] = None


@app.post(f"{settings.API_PREFIX}/refresh-stock-price", response_model=RefreshStockPriceResponse)
async def refresh_stock_price(
    request: RefreshStockPriceRequest,
    current_user: TokenData = Depends(require_admin_or_verifier),
    supabase=Depends(get_db)
):
    """
    Refresh stock price data for a specific security ID (Admin/Verifier only)
    
    This endpoint fetches fresh data from Dhan API for the period 2015-01-01 to today.
    It deletes existing records for the security in this date range and inserts new data.
    
    Args:
        request: Contains securityid
        current_user: Authenticated admin or verifier user
        
    Returns:
        Success status with metadata about the refresh operation
    """
    try:
        # Import from local helper module in verification_system directory
        from stockpricedata_helper import refresh_stock_price_data_by_security_id
        
        logger.info(f"✅ Successfully imported stockpricedata_helper module")
        
        logger.info(f"User {current_user.email} (ID: {current_user.user_id}) refreshing stock price data for security ID: {request.securityid}")
        
        # Call the refresh function with hardcoded date range
        result = refresh_stock_price_data_by_security_id(
            security_id=request.securityid,
            from_date="2015-01-01",
            to_date=datetime.utcnow().strftime("%Y-%m-%d")
        )
        
        # Build response message
        if result.get("success"):
            message = f"Successfully refreshed stock price data for {result.get('symbol', 'Unknown')} (Security ID: {request.securityid}). Fetched {result.get('records_fetched', 0)} records."
            logger.info(f"✅ {message}")
        else:
            message = f"Failed to refresh stock price data for security ID {request.securityid}"
            error_detail = result.get('error', 'Unknown error')
            logger.error(f"❌ {message}: {error_detail}")
        
        # Log the operation to audit trail (optional - can be added later)
        # You can create a stock_price_refresh_audit table to track these operations
        
        return RefreshStockPriceResponse(
            success=result.get("success", False),
            securityid=request.securityid,
            symbol=result.get("symbol"),
            isin=result.get("isin"),
            exchange=result.get("exchange"),
            records_fetched=result.get("records_fetched"),
            from_date=result.get("from_date"),
            to_date=result.get("to_date"),
            message=message,
            error=result.get("error")
        )
        
    except ImportError as e:
        logger.error(f"Failed to import stockpricedata module: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stock price refresh service unavailable: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Stock price refresh error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh stock price data: {str(e)}"
        )


# ============================================================================
# Corporate Actions Endpoint
# ============================================================================

@app.get(f"{settings.API_PREFIX}/corporate-actions")
async def get_corporate_actions(
    page: int = 1,
    page_size: int = 50,
    exchange: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    symbol: Optional[str] = None,
    current_user: TokenData = Depends(require_admin_or_verifier),
    supabase=Depends(get_db)
):
    """
    Get corporate actions data where action_required = true (Admin/Verifier only)
    
    This endpoint returns corporate actions that require investor action,
    such as bonus issues, rights issues, stock splits, etc.
    
    Args:
        page: Page number (default: 1)
        page_size: Records per page (max: 100, default: 50)
        exchange: Filter by exchange (NSE or BSE)
        start_date: Filter by ex_date >= start_date (YYYY-MM-DD)
        end_date: Filter by ex_date <= end_date (YYYY-MM-DD)
        symbol: Filter by stock symbol
        current_user: Authenticated admin or verifier user
        
    Returns:
        Paginated list of corporate actions with action_required = true
    """
    try:
        # Validate pagination
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50
        elif page_size > 100:
            page_size = 100
            
        offset = (page - 1) * page_size
        
        logger.info(f"User {current_user.email} fetching corporate actions: page={page}, page_size={page_size}")
        
        # Build query - only action_required = true
        query = supabase.table("corporate_actions")\
            .select("*", count="exact")\
            .eq("action_required", True)
        
        # Apply filters
        if exchange:
            if exchange.upper() not in ["NSE", "BSE"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Exchange must be either 'NSE' or 'BSE'"
                )
            query = query.eq("exchange", exchange.upper())
        
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                query = query.gte("ex_date", start_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use YYYY-MM-DD"
                )
        
        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
                query = query.lte("ex_date", end_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use YYYY-MM-DD"
                )
        
        if symbol:
            query = query.ilike("symbol", f"%{symbol}%")
        
        # Apply ordering and pagination
        query = query.order("ex_date", desc=True)\
                     .order("created_at", desc=True)\
                     .range(offset, offset + page_size - 1)
        
        result = query.execute()
        
        total_count = result.count if hasattr(result, 'count') else 0
        total_pages = (total_count + page_size - 1) // page_size if total_count else 0
        
        logger.info(f"Found {len(result.data)} corporate actions (page {page}/{total_pages}, total: {total_count})")
        
        return {
            "success": True,
            "corporate_actions": result.data,
            "count": len(result.data),
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "has_next": page < total_pages,
            "has_previous": page > 1,
            "filters": {
                "action_required": True,
                "exchange": exchange,
                "start_date": start_date,
                "end_date": end_date,
                "symbol": symbol
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get corporate actions error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch corporate actions: {str(e)}"
        )


# ============================================================================
# Deals Verification Endpoints
# ============================================================================

@app.get(f"{settings.API_PREFIX}/deals/pending")
async def get_pending_deals(
    skip: int = 0,
    limit: int = 50,
    exchange: Optional[str] = None,
    deal: Optional[str] = None,
    supabase=Depends(get_db),
    current_user=Depends(require_admin_or_verifier)
):
    """
    Get list of pending deals for verification
    
    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        exchange: Filter by exchange (NSE/BSE)
        deal: Filter by deal type (BULK/BLOCK)
    """
    try:
        query = supabase.table("deals_pending_verification")\
            .select("*")\
            .eq("verification_status", "pending")\
            .order("created_at", desc=False)\
            .range(skip, skip + limit - 1)
        
        # Apply filters if provided
        if exchange:
            query = query.eq("exchange", exchange.upper())
        if deal:
            query = query.eq("deal", deal.upper())
        
        result = query.execute()
        
        return {
            "success": True,
            "deals": result.data or [],
            "count": len(result.data) if result.data else 0
        }
    except Exception as e:
        logger.error(f"Error fetching pending deals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending deals: {str(e)}"
        )


@app.post(f"{settings.API_PREFIX}/deals/{{deal_id}}/claim")
async def claim_deal(
    deal_id: str,
    supabase=Depends(get_db),
    current_user=Depends(require_admin_or_verifier)
):
    """
    Claim a deal for verification
    
    This marks the deal as claimed by the current user
    """
    try:
        # Check if deal exists and is pending
        existing = supabase.table("deals_pending_verification")\
            .select("*")\
            .eq("id", deal_id)\
            .execute()
        
        if not existing.data or len(existing.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deal not found"
            )
        
        deal = existing.data[0]
        
        if deal["verification_status"] == "claimed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deal already claimed by user {deal.get('claimed_by')}"
            )
        
        if deal["verification_status"] != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deal is already {deal['verification_status']}"
            )
        
        # Claim the deal
        update_data = {
            "verification_status": "claimed",
            "claimed_by": current_user.user_id,
            "claimed_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("deals_pending_verification")\
            .update(update_data)\
            .eq("id", deal_id)\
            .execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to claim deal"
            )
        
        return {
            "success": True,
            "message": "Deal claimed successfully",
            "deal": result.data[0]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error claiming deal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to claim deal: {str(e)}"
        )


@app.get(f"{settings.API_PREFIX}/deals/{{deal_id}}")
async def get_deal_details(
    deal_id: str,
    supabase=Depends(get_db),
    current_user=Depends(require_admin_or_verifier)
):
    """Get detailed information about a specific deal"""
    try:
        result = supabase.table("deals_pending_verification")\
            .select("*")\
            .eq("id", deal_id)\
            .execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deal not found"
            )
        
        return {
            "success": True,
            "deal": result.data[0]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching deal details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deal details: {str(e)}"
        )


@app.put(f"{settings.API_PREFIX}/deals/{{deal_id}}")
async def update_deal(
    deal_id: str,
    update_req: DealUpdateRequest,
    supabase=Depends(get_db),
    current_user=Depends(require_admin_or_verifier)
):
    """
    Update deal fields before verification
    
    Only deals claimed by the current user can be edited
    """
    try:
        # Check if deal exists and is claimed by current user
        existing = supabase.table("deals_pending_verification")\
            .select("*")\
            .eq("id", deal_id)\
            .execute()
        
        if not existing.data or len(existing.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deal not found"
            )
        
        deal = existing.data[0]
        
        # Check if deal is claimed by current user or user is admin
        if deal["claimed_by"] != current_user.user_id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only edit deals claimed by you"
            )
        
        if deal["verification_status"] not in ["pending", "claimed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot edit deal with status: {deal['verification_status']}"
            )
        
        # Build update data (only include provided fields)
        update_data = {}
        for field, value in update_req.dict(exclude_unset=True).items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Update the deal
        result = supabase.table("deals_pending_verification")\
            .update(update_data)\
            .eq("id", deal_id)\
            .execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update deal"
            )
        
        return {
            "success": True,
            "message": "Deal updated successfully",
            "deal": result.data[0]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating deal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update deal: {str(e)}"
        )


@app.post(f"{settings.API_PREFIX}/deals/{{deal_id}}/verify")
async def verify_deal(
    deal_id: str,
    verify_req: DealVerifyRequest,
    supabase=Depends(get_db),
    current_user=Depends(require_admin_or_verifier)
):
    """
    Verify a deal and insert it into the deals table
    
    This marks the deal as verified and inserts it into the final deals table
    """
    try:
        # Get the deal
        result = supabase.table("deals_pending_verification")\
            .select("*")\
            .eq("id", deal_id)\
            .execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deal not found"
            )
        
        deal = result.data[0]
        
        # Check if deal is claimed by current user or user is admin
        if deal["claimed_by"] != current_user.user_id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only verify deals claimed by you"
            )
        
        if deal["verification_status"] not in ["pending", "claimed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deal is already {deal['verification_status']}"
            )
        
        # Prepare data for deals table
        deal_data = {
            "symbol": deal["symbol"],
            "securityid": deal["securityid"],
            "date": deal["date"],
            "client_name": deal["client_name"],
            "deal_type": deal["deal_type"],
            "quantity": deal["quantity"],
            "price": deal["price"],
            "exchange": deal["exchange"],
            "deal": deal["deal"]
        }
        
        # Insert into deals table (trigger will auto-populate securityid if needed)
        insert_result = supabase.table("deals").insert(deal_data).execute()
        
        if not insert_result.data or len(insert_result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to insert deal into deals table"
            )
        
        # Update verification status
        update_data = {
            "verification_status": "verified",
            "verified_by": current_user.user_id,
            "verified_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("deals_pending_verification")\
            .update(update_data)\
            .eq("id", deal_id)\
            .execute()
        
        return {
            "success": True,
            "message": "Deal verified and inserted successfully",
            "deal": insert_result.data[0]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying deal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify deal: {str(e)}"
        )


@app.post(f"{settings.API_PREFIX}/deals/{{deal_id}}/reject")
async def reject_deal(
    deal_id: str,
    reject_req: DealRejectRequest,
    supabase=Depends(get_db),
    current_user=Depends(require_admin_or_verifier)
):
    """
    Reject a deal with a reason
    
    This marks the deal as rejected and removes it from the verification queue
    """
    try:
        # Get the deal
        result = supabase.table("deals_pending_verification")\
            .select("*")\
            .eq("id", deal_id)\
            .execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deal not found"
            )
        
        deal = result.data[0]
        
        # Check if deal is claimed by current user or user is admin
        if deal["claimed_by"] != current_user.user_id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only reject deals claimed by you"
            )
        
        if deal["verification_status"] not in ["pending", "claimed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deal is already {deal['verification_status']}"
            )
        
        # Update verification status to rejected
        update_data = {
            "verification_status": "rejected",
            "verified_by": current_user.user_id,
            "verified_at": datetime.utcnow().isoformat(),
            "rejection_reason": reject_req.reason
        }
        
        result = supabase.table("deals_pending_verification")\
            .update(update_data)\
            .eq("id", deal_id)\
            .execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reject deal"
            )
        
        return {
            "success": True,
            "message": "Deal rejected successfully",
            "deal": result.data[0]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting deal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject deal: {str(e)}"
        )


@app.post(f"{settings.API_PREFIX}/deals/{{deal_id}}/release")
async def release_deal(
    deal_id: str,
    supabase=Depends(get_db),
    current_user=Depends(require_admin_or_verifier)
):
    """
    Release a claimed deal back to pending status
    
    Useful if a verifier can't complete the verification
    """
    try:
        # Get the deal
        result = supabase.table("deals_pending_verification")\
            .select("*")\
            .eq("id", deal_id)\
            .execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deal not found"
            )
        
        deal = result.data[0]
        
        # Check if deal is claimed by current user or user is admin
        if deal["claimed_by"] != current_user.user_id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only release deals claimed by you"
            )
        
        if deal["verification_status"] != "claimed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only release claimed deals"
            )
        
        # Release the deal
        update_data = {
            "verification_status": "pending",
            "claimed_by": None,
            "claimed_at": None
        }
        
        result = supabase.table("deals_pending_verification")\
            .update(update_data)\
            .eq("id", deal_id)\
            .execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to release deal"
            )
        
        return {
            "success": True,
            "message": "Deal released successfully",
            "deal": result.data[0]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error releasing deal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to release deal: {str(e)}"
        )


@app.get(f"{settings.API_PREFIX}/deals/stats")
async def get_deals_stats(
    supabase=Depends(get_db),
    current_user=Depends(require_admin_or_verifier)
):
    """Get statistics about deals verification queue"""
    try:
        result = supabase.table("deals_verification_stats").select("*").execute()
        
        if not result.data or len(result.data) == 0:
            return {
                "success": True,
                "stats": {
                    "pending_verification": 0,
                    "currently_claimed": 0,
                    "verified": 0,
                    "rejected": 0,
                    "bulk_deals": 0,
                    "block_deals": 0,
                    "nse_deals": 0,
                    "bse_deals": 0
                }
            }
        
        return {
            "success": True,
            "stats": result.data[0]
        }
    except Exception as e:
        logger.error(f"Error fetching deals stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deals stats: {str(e)}"
        )


# ============================================================================
# Application Startup
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info(f"🚀 Starting {settings.APP_NAME}")
    logger.info(f"📍 Environment: {'Production' if settings.PROD else 'Development'}")
    logger.info(f"🌐 API: http://{settings.HOST}:{settings.PORT}{settings.API_PREFIX}")
    
    # Test database connection
    try:
        supabase = get_db()
        logger.info("✅ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=not settings.PROD
    )
