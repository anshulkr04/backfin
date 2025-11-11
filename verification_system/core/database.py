#!/usr/bin/env python3
"""
Database integration for verification system using Supabase
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import uuid
import json

try:
    from supabase import create_client, Client
    import asyncpg
except ImportError:
    print("Missing dependencies. Install with: pip install supabase asyncpg")
    raise

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress" 
    VERIFIED = "verified"

@dataclass
class AdminUser:
    id: str
    email: str
    name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    password_hash: Optional[str] = None
    registration_token: Optional[str] = None

@dataclass
class AdminSession:
    id: str
    user_id: str
    session_token: str
    expires_at: datetime
    is_active: bool
    last_activity: datetime
    user_agent: Optional[str]
    ip_address: Optional[str]
    created_at: datetime

@dataclass
class VerificationTask:
    id: str
    announcement_id: str
    original_data: Dict[str, Any]
    current_data: Dict[str, Any]
    has_edits: bool
    edit_count: int
    status: TaskStatus
    assigned_to_session: Optional[str]
    assigned_to_user: Optional[str]
    assigned_at: Optional[datetime]
    is_verified: Optional[bool]
    verified_by: Optional[str]
    verified_at: Optional[datetime]
    verification_notes: Optional[str]
    retry_count: int
    timeout_count: int
    created_at: datetime
    updated_at: datetime

@dataclass
class VerificationEdit:
    id: str
    task_id: str
    field_name: str
    original_value: Optional[str]
    current_value: Optional[str]
    edited_by: str
    edited_at: datetime
    edit_reason: Optional[str]

class DatabaseManager:
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Missing SUPABASE_URL or SUPABASE_ANON_KEY environment variables")
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        self.pool = None
        
    async def connect(self):
        """Initialize database connection pool"""
        try:
            # Test connection with a simple query
            result = self.client.table('admin_users').select('id').limit(1).execute()
            logger.info("✅ Connected to Supabase successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Supabase: {e}")
            return False

    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            
    # ============================================================================
    # Admin Users Management
    # ============================================================================
    
    async def create_admin_user(self, email: str, password_hash: str, name: str) -> AdminUser:
        """Create a new admin user"""
        try:
            user_data = {
                'email': email,
                'password_hash': password_hash,
                'name': name,
                'is_active': True,
                'is_verified': False,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            result = self.client.table('admin_users').insert(user_data).execute()
            data = result.data[0]
            
            return AdminUser(
                id=data['id'],
                email=data['email'],
                name=data['name'],
                is_active=data['is_active'],
                is_verified=data['is_verified'],
                created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00')),
                password_hash=data['password_hash']
            )
            
        except Exception as e:
            logger.error(f"❌ Error creating admin user: {e}")
            raise
    
    async def get_admin_user_by_email(self, email: str) -> Optional[AdminUser]:
        """Get admin user by email"""
        try:
            result = self.client.table('admin_users').select('*').eq('email', email).execute()
            
            if not result.data:
                return None
                
            data = result.data[0]
            return AdminUser(
                id=data['id'],
                email=data['email'],
                name=data['name'],
                is_active=data['is_active'],
                is_verified=data['is_verified'],
                created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00')),
                password_hash=data['password_hash']
            )
            
        except Exception as e:
            logger.error(f"❌ Error getting admin user: {e}")
            return None

    async def get_admin_user_by_id(self, user_id: str) -> Optional[AdminUser]:
        """Get admin user by ID"""
        try:
            result = self.client.table('admin_users').select('*').eq('id', user_id).execute()
            
            if not result.data:
                return None
                
            data = result.data[0]
            return AdminUser(
                id=data['id'],
                email=data['email'],
                name=data['name'],
                is_active=data['is_active'],
                is_verified=data['is_verified'],
                created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
            )
            
        except Exception as e:
            logger.error(f"❌ Error getting admin user by ID: {e}")
            return None

    # ============================================================================
    # Admin Sessions Management
    # ============================================================================
    
    async def create_admin_session(
        self,
        user_id: str,
        session_token: str,
        expires_at: datetime,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> AdminSession:
        """Create a new admin session"""
        try:
            session_data = {
                'user_id': user_id,
                'session_token': session_token,
                'expires_at': expires_at.isoformat(),
                'is_active': True,
                'last_activity': datetime.utcnow().isoformat(),
                'user_agent': user_agent,
                'ip_address': ip_address,
                'created_at': datetime.utcnow().isoformat()
            }
            
            result = self.client.table('admin_sessions').insert(session_data).execute()
            data = result.data[0]
            
            return AdminSession(
                id=data['id'],
                user_id=data['user_id'],
                session_token=data['session_token'],
                expires_at=datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00')),
                is_active=data['is_active'],
                last_activity=datetime.fromisoformat(data['last_activity'].replace('Z', '+00:00')),
                user_agent=data['user_agent'],
                ip_address=data['ip_address'],
                created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
            )
            
        except Exception as e:
            logger.error(f"❌ Error creating admin session: {e}")
            raise

    async def get_admin_session(self, session_token: str) -> Optional[AdminSession]:
        """Get admin session by token"""
        try:
            result = self.client.table('admin_sessions').select('*').eq('session_token', session_token).eq('is_active', True).execute()
            
            if not result.data:
                return None
                
            data = result.data[0]
            session = AdminSession(
                id=data['id'],
                user_id=data['user_id'],
                session_token=data['session_token'],
                expires_at=datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00')),
                is_active=data['is_active'],
                last_activity=datetime.fromisoformat(data['last_activity'].replace('Z', '+00:00')),
                user_agent=data['user_agent'],
                ip_address=data['ip_address'],
                created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
            )
            
            # Check if session is expired
            if session.expires_at < datetime.utcnow():
                await self.expire_admin_session(session_token)
                return None
                
            return session
            
        except Exception as e:
            logger.error(f"❌ Error getting admin session: {e}")
            return None

    async def update_session_activity(self, session_token: str) -> bool:
        """Update last activity for a session"""
        try:
            result = self.client.table('admin_sessions').update({
                'last_activity': datetime.utcnow().isoformat()
            }).eq('session_token', session_token).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"❌ Error updating session activity: {e}")
            return False

    async def expire_admin_session(self, session_token: str) -> bool:
        """Expire an admin session"""
        try:
            result = self.client.table('admin_sessions').update({
                'is_active': False
            }).eq('session_token', session_token).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"❌ Error expiring admin session: {e}")
            return False

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        try:
            cutoff_time = datetime.utcnow().isoformat()
            
            result = self.client.table('admin_sessions').update({
                'is_active': False
            }).lt('expires_at', cutoff_time).eq('is_active', True).execute()
            
            count = len(result.data) if result.data else 0
            if count > 0:
                logger.info(f"🧹 Cleaned up {count} expired sessions")
            
            return count
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up expired sessions: {e}")
            return 0

    # ============================================================================
    # Verification Tasks Management
    # ============================================================================
    
    async def create_verification_task(
        self,
        announcement_id: str,
        original_data: Dict[str, Any],
        current_data: Optional[Dict[str, Any]] = None
    ) -> VerificationTask:
        """Create a new verification task"""
        try:
            if current_data is None:
                current_data = original_data.copy()
            
            task_data = {
                'announcement_id': announcement_id,
                'original_data': json.dumps(original_data),
                'current_data': json.dumps(current_data),
                'has_edits': False,
                'edit_count': 0,
                'status': TaskStatus.QUEUED.value,
                'retry_count': 0,
                'timeout_count': 0,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            result = self.client.table('verification_tasks').insert(task_data).execute()
            data = result.data[0]
            
            return self._row_to_verification_task(data)
            
        except Exception as e:
            logger.error(f"❌ Error creating verification task: {e}")
            raise

    async def get_verification_tasks(
        self,
        status: Optional[TaskStatus] = None,
        assigned_to_user: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[VerificationTask]:
        """Get verification tasks with filters"""
        try:
            query = self.client.table('verification_tasks').select('*')
            
            if status:
                query = query.eq('status', status.value)
            
            if assigned_to_user:
                query = query.eq('assigned_to_user', assigned_to_user)
            
            result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
            
            return [self._row_to_verification_task(row) for row in result.data]
            
        except Exception as e:
            logger.error(f"❌ Error getting verification tasks: {e}")
            return []

    async def get_verification_task(self, task_id: str) -> Optional[VerificationTask]:
        """Get a specific verification task"""
        try:
            result = self.client.table('verification_tasks').select('*').eq('id', task_id).execute()
            
            if not result.data:
                return None
                
            return self._row_to_verification_task(result.data[0])
            
        except Exception as e:
            logger.error(f"❌ Error getting verification task: {e}")
            return None

    async def claim_verification_task(
        self,
        user_id: str,
        session_id: str
    ) -> Optional[VerificationTask]:
        """Claim the next available verification task atomically"""
        try:
            # First get the next available task
            result = self.client.table('verification_tasks').select('*').eq('status', TaskStatus.QUEUED.value).order('created_at').limit(1).execute()
            
            if not result.data:
                return None
            
            task_id = result.data[0]['id']
            
            # Try to claim it atomically
            now = datetime.utcnow().isoformat()
            update_result = self.client.table('verification_tasks').update({
                'status': TaskStatus.IN_PROGRESS.value,
                'assigned_to_user': user_id,
                'assigned_to_session': session_id,
                'assigned_at': now,
                'updated_at': now
            }).eq('id', task_id).eq('status', TaskStatus.QUEUED.value).execute()
            
            if not update_result.data:
                # Task was claimed by someone else
                return None
                
            return self._row_to_verification_task(update_result.data[0])
            
        except Exception as e:
            logger.error(f"❌ Error claiming verification task: {e}")
            return None

    async def update_verification_task(
        self,
        task_id: str,
        current_data: Optional[Dict[str, Any]] = None,
        status: Optional[TaskStatus] = None,
        is_verified: Optional[bool] = None,
        verified_by: Optional[str] = None,
        verification_notes: Optional[str] = None
    ) -> Optional[VerificationTask]:
        """Update a verification task"""
        try:
            update_data = {'updated_at': datetime.utcnow().isoformat()}
            
            if current_data is not None:
                update_data['current_data'] = json.dumps(current_data)
            
            if status is not None:
                update_data['status'] = status.value
                
            if is_verified is not None:
                update_data['is_verified'] = is_verified
                
            if verified_by is not None:
                update_data['verified_by'] = verified_by
                
            if verification_notes is not None:
                update_data['verification_notes'] = verification_notes
            
            if is_verified:
                update_data['verified_at'] = datetime.utcnow().isoformat()
            
            result = self.client.table('verification_tasks').update(update_data).eq('id', task_id).execute()
            
            if not result.data:
                return None
                
            return self._row_to_verification_task(result.data[0])
            
        except Exception as e:
            logger.error(f"❌ Error updating verification task: {e}")
            return None

    async def release_verification_task(self, task_id: str) -> bool:
        """Release a verification task back to the queue"""
        try:
            result = self.client.table('verification_tasks').update({
                'status': TaskStatus.QUEUED.value,
                'assigned_to_user': None,
                'assigned_to_session': None,
                'assigned_at': None,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', task_id).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"❌ Error releasing verification task: {e}")
            return False

    async def cleanup_orphaned_tasks(self, active_session_ids: List[str]) -> int:
        """Clean up tasks assigned to inactive sessions"""
        try:
            if not active_session_ids:
                # If no active sessions, release all in-progress tasks
                result = self.client.table('verification_tasks').update({
                    'status': TaskStatus.QUEUED.value,
                    'assigned_to_user': None,
                    'assigned_to_session': None,
                    'assigned_at': None,
                    'updated_at': datetime.utcnow().isoformat(),
                    'timeout_count': 'timeout_count + 1'
                }).eq('status', TaskStatus.IN_PROGRESS.value).execute()
            else:
                # Release tasks assigned to inactive sessions
                result = self.client.table('verification_tasks').update({
                    'status': TaskStatus.QUEUED.value,
                    'assigned_to_user': None,
                    'assigned_to_session': None,
                    'assigned_at': None,
                    'updated_at': datetime.utcnow().isoformat(),
                    'timeout_count': 'timeout_count + 1'
                }).eq('status', TaskStatus.IN_PROGRESS.value).not_.in_('assigned_to_session', active_session_ids).execute()
            
            count = len(result.data) if result.data else 0
            if count > 0:
                logger.info(f"🧹 Released {count} orphaned tasks")
                
            return count
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up orphaned tasks: {e}")
            return 0

    # ============================================================================
    # Verification Edits Management
    # ============================================================================
    
    async def create_verification_edit(
        self,
        task_id: str,
        field_name: str,
        original_value: Optional[str],
        current_value: Optional[str],
        edited_by: str,
        edit_reason: Optional[str] = None
    ) -> VerificationEdit:
        """Create a verification edit record"""
        try:
            edit_data = {
                'task_id': task_id,
                'field_name': field_name,
                'original_value': original_value,
                'current_value': current_value,
                'edited_by': edited_by,
                'edited_at': datetime.utcnow().isoformat(),
                'edit_reason': edit_reason
            }
            
            result = self.client.table('verification_edits').insert(edit_data).execute()
            data = result.data[0]
            
            # Update task edit count and has_edits flag
            await self.client.table('verification_tasks').update({
                'has_edits': True,
                'edit_count': 'edit_count + 1',
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', task_id).execute()
            
            return VerificationEdit(
                id=data['id'],
                task_id=data['task_id'],
                field_name=data['field_name'],
                original_value=data['original_value'],
                current_value=data['current_value'],
                edited_by=data['edited_by'],
                edited_at=datetime.fromisoformat(data['edited_at'].replace('Z', '+00:00')),
                edit_reason=data['edit_reason']
            )
            
        except Exception as e:
            logger.error(f"❌ Error creating verification edit: {e}")
            raise

    async def get_verification_edits(self, task_id: str) -> List[VerificationEdit]:
        """Get all edits for a verification task"""
        try:
            result = self.client.table('verification_edits').select('*').eq('task_id', task_id).order('edited_at').execute()
            
            return [
                VerificationEdit(
                    id=row['id'],
                    task_id=row['task_id'],
                    field_name=row['field_name'],
                    original_value=row['original_value'],
                    current_value=row['current_value'],
                    edited_by=row['edited_by'],
                    edited_at=datetime.fromisoformat(row['edited_at'].replace('Z', '+00:00')),
                    edit_reason=row['edit_reason']
                )
                for row in result.data
            ]
            
        except Exception as e:
            logger.error(f"❌ Error getting verification edits: {e}")
            return []

    # ============================================================================
    # Activity Logging
    # ============================================================================
    
    async def log_admin_activity(
        self,
        user_id: Optional[str],
        session_id: Optional[str],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Log admin activity"""
        try:
            activity_data = {
                'user_id': user_id,
                'session_id': session_id,
                'action': action,
                'resource_type': resource_type,
                'resource_id': resource_id,
                'details': json.dumps(details) if details else None,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'created_at': datetime.utcnow().isoformat()
            }
            
            self.client.table('admin_activity_log').insert(activity_data).execute()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error logging admin activity: {e}")
            return False

    # ============================================================================
    # Statistics
    # ============================================================================
    
    async def get_verification_stats(self) -> Dict[str, Any]:
        """Get verification statistics"""
        try:
            stats = {}
            
            # Task counts by status
            for status in TaskStatus:
                result = self.client.table('verification_tasks').select('id', count='exact').eq('status', status.value).execute()
                stats[f"tasks_{status.value}"] = result.count or 0
            
            # Active sessions count
            result = self.client.table('admin_sessions').select('id', count='exact').eq('is_active', True).gt('expires_at', datetime.utcnow().isoformat()).execute()
            stats['active_sessions'] = result.count or 0
            
            # Total edits
            result = self.client.table('verification_edits').select('id', count='exact').execute()
            stats['total_edits'] = result.count or 0
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting verification stats: {e}")
            return {}

    # ============================================================================
    # Helper Methods
    # ============================================================================
    
    def _row_to_verification_task(self, row: Dict[str, Any]) -> VerificationTask:
        """Convert database row to VerificationTask object"""
        return VerificationTask(
            id=row['id'],
            announcement_id=row['announcement_id'],
            original_data=json.loads(row['original_data']) if row['original_data'] else {},
            current_data=json.loads(row['current_data']) if row['current_data'] else {},
            has_edits=row['has_edits'],
            edit_count=row['edit_count'],
            status=TaskStatus(row['status']),
            assigned_to_session=row['assigned_to_session'],
            assigned_to_user=row['assigned_to_user'],
            assigned_at=datetime.fromisoformat(row['assigned_at'].replace('Z', '+00:00')) if row['assigned_at'] else None,
            is_verified=row['is_verified'],
            verified_by=row['verified_by'],
            verified_at=datetime.fromisoformat(row['verified_at'].replace('Z', '+00:00')) if row['verified_at'] else None,
            verification_notes=row['verification_notes'],
            retry_count=row['retry_count'],
            timeout_count=row['timeout_count'],
            created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
        )