import os
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import json

logger = logging.getLogger(__name__)

class MockSupabaseService:
    """Mock Supabase service for testing without database"""
    
    def __init__(self):
        self.users = {}
        self.sessions = {}
        self.tasks = {}
        self.edits = {}
        self.activities = {}
        logger.info("🧪 Using Mock Supabase Service for testing")
    
    # User management
    async def create_user(self, email: str, password_hash: str, name: str):
        """Create a new admin user"""
        user_id = str(uuid.uuid4())
        user_data = {
            "id": user_id,
            "email": email,
            "password_hash": password_hash,
            "name": name,
            "is_active": True,
            "is_verified": True,
            "created_at": datetime.utcnow().isoformat()
        }
        self.users[user_id] = user_data
        logger.info(f"✅ Mock: Created user {email}")
        return user_data
    
    async def get_user_by_email(self, email: str):
        """Get user by email"""
        for user in self.users.values():
            if user["email"] == email:
                return user
        return None
    
    async def get_user_by_id(self, user_id: str):
        """Get user by ID"""
        return self.users.get(user_id)
    
    # Session management
    async def create_session(self, user_id: str, session_token: str) -> str:
        """Create a new session"""
        session_id = str(uuid.uuid4())
        session_data = {
            "id": session_id,
            "user_id": user_id,
            "session_token": session_token,
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat()
        }
        self.sessions[session_id] = session_data
        logger.info(f"✅ Mock: Created session for user {user_id}")
        return session_id
    
    async def get_session_by_token(self, session_token: str):
        """Get session by token"""
        for session in self.sessions.values():
            if session["session_token"] == session_token and session["is_active"]:
                return session
        return None
    
    async def invalidate_session(self, session_token: str) -> bool:
        """Invalidate a session"""
        for session in self.sessions.values():
            if session["session_token"] == session_token:
                session["is_active"] = False
                logger.info("✅ Mock: Session invalidated")
                return True
        return False
    
    # Task management
    async def get_task_by_id(self, task_id: str):
        """Get task by ID"""
        task = self.tasks.get(task_id)
        if task:
            # Convert to object-like structure
            class MockTask:
                def __init__(self, data):
                    for key, value in data.items():
                        setattr(self, key, value)
            return MockTask(task)
        return None
    
    async def assign_task_to_user(self, task_id: str, user_id: str, session_id: str) -> bool:
        """Assign task to user"""
        if task_id in self.tasks:
            self.tasks[task_id]["assigned_to_user"] = user_id
            self.tasks[task_id]["status"] = "in_progress"
            self.tasks[task_id]["assigned_at"] = datetime.utcnow().isoformat()
            logger.info(f"✅ Mock: Assigned task {task_id} to user {user_id}")
            return True
        return False
    
    async def get_user_assigned_count(self, user_id: str) -> int:
        """Get count of tasks assigned to user"""
        count = 0
        for task in self.tasks.values():
            if task.get("assigned_to_user") == user_id and task.get("status") == "in_progress":
                count += 1
        return count
    
    async def release_task(self, task_id: str) -> bool:
        """Release task back to queue"""
        if task_id in self.tasks:
            self.tasks[task_id]["assigned_to_user"] = None
            self.tasks[task_id]["status"] = "pending"
            self.tasks[task_id]["assigned_at"] = None
            logger.info(f"✅ Mock: Released task {task_id}")
            return True
        return False
    
    async def get_task_edits(self, task_id: str) -> List:
        """Get task edit history"""
        edits = []
        for edit in self.edits.values():
            if edit["task_id"] == task_id:
                class MockEdit:
                    def __init__(self, data):
                        for key, value in data.items():
                            setattr(self, key, value)
                edits.append(MockEdit(edit))
        return edits
    
    async def update_task_field(self, task_id: str, field_name: str, new_value: str, user_id: str, reason: str = None):
        """Update a task field"""
        if task_id in self.tasks:
            # Update current data
            current_data = self.tasks[task_id].get("current_data", {})
            if isinstance(current_data, str):
                current_data = json.loads(current_data)
            
            original_value = current_data.get(field_name)
            current_data[field_name] = new_value
            
            self.tasks[task_id]["current_data"] = current_data
            self.tasks[task_id]["has_edits"] = True
            self.tasks[task_id]["edit_count"] = self.tasks[task_id].get("edit_count", 0) + 1
            
            # Add edit record
            edit_id = str(uuid.uuid4())
            edit_data = {
                "id": edit_id,
                "task_id": task_id,
                "field_name": field_name,
                "original_value": original_value,
                "current_value": new_value,
                "edited_by": user_id,
                "edited_at": datetime.utcnow().isoformat(),
                "edit_reason": reason
            }
            self.edits[edit_id] = edit_data
            logger.info(f"✅ Mock: Updated field {field_name} in task {task_id}")
    
    async def complete_verification(self, task_id: str, user_id: str, is_verified: bool, notes: str = None) -> bool:
        """Complete verification of a task"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "verified" if is_verified else "rejected"
            self.tasks[task_id]["verified_by"] = user_id
            self.tasks[task_id]["verified_at"] = datetime.utcnow().isoformat()
            self.tasks[task_id]["verification_notes"] = notes
            self.tasks[task_id]["is_verified"] = is_verified
            logger.info(f"✅ Mock: Completed verification for task {task_id}: {is_verified}")
            return True
        return False
    
    async def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        pending_count = sum(1 for task in self.tasks.values() if task.get("status") == "pending")
        in_progress_count = sum(1 for task in self.tasks.values() if task.get("status") == "in_progress")
        verified_today = sum(1 for task in self.tasks.values() if task.get("status") in ["verified", "rejected"])
        verified_yes_today = sum(1 for task in self.tasks.values() if task.get("is_verified") == True)
        verified_no_today = sum(1 for task in self.tasks.values() if task.get("is_verified") == False)
        
        return {
            "pending_count": pending_count,
            "in_progress_count": in_progress_count,
            "verified_today": verified_today,
            "verified_yes_today": verified_yes_today,
            "verified_no_today": verified_no_today,
            "total_tasks": len(self.tasks)
        }
    
    async def log_activity(self, user_id: str, session_id: str, action: str, resource_type: str = None, resource_id: str = None, details: Dict = None, ip_address: str = None, user_agent: str = None):
        """Log user activity"""
        activity_id = str(uuid.uuid4())
        activity_data = {
            "id": activity_id,
            "user_id": user_id,
            "session_id": session_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.utcnow().isoformat()
        }
        self.activities[activity_id] = activity_data
        logger.debug(f"📝 Mock: Logged activity {action} for user {user_id}")

# Create service instance (will be used as singleton)
try:
    # Try to use real Supabase if configured
    url = os.getenv("SUPABASE_URL2") or os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY2") or os.getenv("SUPABASE_KEY")
    
    if url and key:
        from services.supabase_client import SupabaseService
        supabase_service = SupabaseService()
        logger.info("✅ Using real Supabase service")
    else:
        supabase_service = MockSupabaseService()
        logger.info("🧪 Using mock Supabase service (no credentials found)")
        
except Exception as e:
    logger.warning(f"⚠️ Failed to initialize Supabase, using mock service: {e}")
    supabase_service = MockSupabaseService()