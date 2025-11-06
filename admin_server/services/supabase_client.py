import os
from typing import Optional, List, Dict, Any
from supabase import create_client, Client
from datetime import datetime, timedelta
import uuid
import json

from models.auth import AdminUser, AdminSession
from models.verification import VerificationTask, VerificationEdit

class SupabaseService:
    def __init__(self):
        url = os.getenv("SUPABASE_URL2")  # Using same as main app
        key = os.getenv("SUPABASE_KEY2")  # Using same as main app
        
        if not url or not key:
            raise ValueError("Supabase URL and Key must be provided")
        
        self.client: Client = create_client(url, key)
    
    # User management
    async def create_user(self, email: str, password_hash: str, name: str) -> AdminUser:
        """Create a new admin user"""
        user_data = {
            "email": email,
            "password_hash": password_hash,
            "name": name,
            "is_active": True,
            "is_verified": True  # No email verification needed
        }
        
        result = self.client.table("admin_users").insert(user_data).execute()
        if result.data:
            return AdminUser(**result.data[0])
        else:
            raise Exception("Failed to create user")
    
    async def get_user_by_email(self, email: str) -> Optional[AdminUser]:
        """Get user by email"""
        result = self.client.table("admin_users").select("*").eq("email", email).eq("is_active", True).execute()
        if result.data:
            return AdminUser(**result.data[0])
        return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[AdminUser]:
        """Get user by ID"""
        result = self.client.table("admin_users").select("*").eq("id", user_id).eq("is_active", True).execute()
        if result.data:
            return AdminUser(**result.data[0])
        return None
    
    # Session management
    async def create_session(self, user_id: str, session_token: str, expires_at: datetime, 
                           user_agent: str = None, ip_address: str = None) -> AdminSession:
        """Create a new admin session"""
        session_data = {
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": expires_at.isoformat(),
            "is_active": True,
            "user_agent": user_agent,
            "ip_address": ip_address
        }
        
        result = self.client.table("admin_sessions").insert(session_data).execute()
        if result.data:
            return AdminSession(**result.data[0])
        else:
            raise Exception("Failed to create session")
    
    async def get_session(self, session_id: str) -> Optional[AdminSession]:
        """Get session by ID"""
        result = self.client.table("admin_sessions").select("*").eq("id", session_id).eq("is_active", True).execute()
        if result.data:
            return AdminSession(**result.data[0])
        return None
    
    async def update_session_activity(self, session_id: str):
        """Update session last activity"""
        self.client.table("admin_sessions").update({
            "last_activity": datetime.utcnow().isoformat()
        }).eq("id", session_id).execute()
    
    async def deactivate_session(self, session_id: str):
        """Deactivate a session"""
        self.client.table("admin_sessions").update({
            "is_active": False
        }).eq("id", session_id).execute()
    
    # Verification task management
    async def create_verification_task(self, announcement_id: str, task_data: Dict[str, Any]) -> VerificationTask:
        """Create a new verification task"""
        task_record = {
            "announcement_id": announcement_id,
            "original_data": task_data,
            "current_data": task_data,  # Start with same data
            "has_edits": False,
            "edit_count": 0,
            "status": "queued",
            "retry_count": 0,
            "timeout_count": 0
        }
        
        result = self.client.table("verification_tasks").insert(task_record).execute()
        if result.data:
            return VerificationTask(**result.data[0])
        else:
            raise Exception("Failed to create verification task")
    
    async def get_task_by_id(self, task_id: str) -> Optional[VerificationTask]:
        """Get task by ID"""
        result = self.client.table("verification_tasks").select("*").eq("id", task_id).execute()
        if result.data:
            return VerificationTask(**result.data[0])
        return None
    
    async def assign_task_to_user(self, task_id: str, user_id: str, session_id: str) -> bool:
        """Assign a task to a user"""
        result = self.client.table("verification_tasks").update({
            "status": "in_progress",
            "assigned_to_user": user_id,
            "assigned_to_session": session_id,
            "assigned_at": datetime.utcnow().isoformat()
        }).eq("id", task_id).eq("status", "queued").execute()
        
        return len(result.data) > 0
    
    async def update_task_field(self, task_id: str, field_name: str, new_value: Any, user_id: str, reason: str = None):
        """Update a field in the task and log the edit"""
        # Get current task
        task = await self.get_task_by_id(task_id)
        if not task:
            raise Exception("Task not found")
        
        # Store original value for edit log
        original_value = task.original_data.get(field_name)
        
        # Update current_data
        current_data = task.current_data.copy()
        current_data[field_name] = new_value
        
        # Update task
        self.client.table("verification_tasks").update({
            "current_data": current_data,
            "has_edits": True,
            "edit_count": task.edit_count + 1
        }).eq("id", task_id).execute()
        
        # Log the edit
        await self.log_edit(task_id, field_name, original_value, new_value, user_id, reason)
    
    async def complete_verification(self, task_id: str, user_id: str, is_verified: bool, notes: str = None) -> bool:
        """Complete verification of a task"""
        result = self.client.table("verification_tasks").update({
            "status": "verified",
            "is_verified": is_verified,
            "verified_by": user_id,
            "verified_at": datetime.utcnow().isoformat(),
            "verification_notes": notes
        }).eq("id", task_id).eq("status", "in_progress").execute()
        
        return len(result.data) > 0
    
    async def release_task(self, task_id: str) -> bool:
        """Release a task back to the queue"""
        result = self.client.table("verification_tasks").update({
            "status": "queued",
            "assigned_to_user": None,
            "assigned_to_session": None,
            "assigned_at": None
        }).eq("id", task_id).eq("status", "in_progress").execute()
        
        return len(result.data) > 0
    
    async def release_stale_tasks(self, timeout_minutes: int = 10) -> int:
        """Release tasks that have been in progress too long"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        
        result = self.client.table("verification_tasks").update({
            "status": "queued",
            "assigned_to_user": None,
            "assigned_to_session": None,
            "assigned_at": None,
            "timeout_count": "timeout_count + 1"  # Increment timeout count
        }).eq("status", "in_progress").lt("assigned_at", cutoff_time.isoformat()).execute()
        
        return len(result.data)
    
    async def log_edit(self, task_id: str, field_name: str, original_value: Any, current_value: Any, 
                      user_id: str, reason: str = None):
        """Log an edit to the verification_edits table"""
        edit_data = {
            "task_id": task_id,
            "field_name": field_name,
            "original_value": str(original_value) if original_value is not None else None,
            "current_value": str(current_value) if current_value is not None else None,
            "edited_by": user_id,
            "edit_reason": reason
        }
        
        self.client.table("verification_edits").insert(edit_data).execute()
    
    async def get_task_edits(self, task_id: str) -> List[VerificationEdit]:
        """Get all edits for a task"""
        result = self.client.table("verification_edits").select("*").eq("task_id", task_id).order("edited_at").execute()
        return [VerificationEdit(**edit) for edit in result.data]
    
    # Statistics
    async def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        # Get counts by status
        pending = self.client.table("verification_tasks").select("id", count="exact").eq("status", "queued").execute()
        in_progress = self.client.table("verification_tasks").select("id", count="exact").eq("status", "in_progress").execute()
        
        # Get today's verifications
        today = datetime.utcnow().date()
        verified_today = self.client.table("verification_tasks").select("id", count="exact").eq("status", "verified").gte("verified_at", today.isoformat()).execute()
        
        verified_yes_today = self.client.table("verification_tasks").select("id", count="exact").eq("status", "verified").eq("is_verified", True).gte("verified_at", today.isoformat()).execute()
        
        verified_no_today = self.client.table("verification_tasks").select("id", count="exact").eq("status", "verified").eq("is_verified", False).gte("verified_at", today.isoformat()).execute()
        
        total = self.client.table("verification_tasks").select("id", count="exact").execute()
        
        return {
            "pending_count": pending.count or 0,
            "in_progress_count": in_progress.count or 0,
            "verified_today": verified_today.count or 0,
            "verified_yes_today": verified_yes_today.count or 0,
            "verified_no_today": verified_no_today.count or 0,
            "total_tasks": total.count or 0
        }
    
    async def get_user_assigned_count(self, user_id: str) -> int:
        """Get number of tasks assigned to a user"""
        result = self.client.table("verification_tasks").select("id", count="exact").eq("assigned_to_user", user_id).eq("status", "in_progress").execute()
        return result.count or 0
    
    # Activity logging
    async def log_activity(self, user_id: str, session_id: str, action: str, 
                          resource_type: str = None, resource_id: str = None, 
                          details: Dict[str, Any] = None, ip_address: str = None, user_agent: str = None):
        """Log admin activity"""
        activity_data = {
            "user_id": user_id,
            "session_id": session_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        
        self.client.table("admin_activity_log").insert(activity_data).execute()

# Global instance
supabase_service = SupabaseService()