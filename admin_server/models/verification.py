from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

# Request models
class TaskClaimRequest(BaseModel):
    pass  # No body needed for claiming next task

class FieldEditRequest(BaseModel):
    field: str
    value: Any
    reason: Optional[str] = None

class TaskVerifyRequest(BaseModel):
    verified: bool
    notes: Optional[str] = None

class TaskVerifyWithChangesRequest(BaseModel):
    action: str  # 'approved', 'approved_with_changes', 'needs_revision'
    changes: Dict[str, Any] = {}
    notes: Optional[str] = None

class TaskReleaseRequest(BaseModel):
    reason: Optional[str] = None

# Response models
class TaskResponse(BaseModel):
    id: str
    announcement_id: str
    original_data: Dict[str, Any]
    current_data: Dict[str, Any]
    has_edits: bool
    edit_count: int
    status: str
    assigned_to_user: Optional[str] = None
    assigned_at: Optional[datetime] = None
    created_at: datetime
    changes: List[Dict[str, Any]] = []

class TaskStatsResponse(BaseModel):
    pending_count: int
    in_progress_count: int
    verified_today: int
    verified_yes_today: int
    verified_no_today: int
    total_tasks: int
    my_assigned_count: int

class VerificationEditResponse(BaseModel):
    id: str
    field_name: str
    original_value: Optional[str]
    current_value: Optional[str]
    edited_by: str
    edited_at: datetime
    edit_reason: Optional[str]

# Internal models
class VerificationTask(BaseModel):
    id: uuid.UUID
    announcement_id: uuid.UUID
    original_data: Dict[str, Any]
    current_data: Dict[str, Any]
    has_edits: bool
    edit_count: int
    status: str
    assigned_to_session: Optional[uuid.UUID] = None
    assigned_to_user: Optional[uuid.UUID] = None
    assigned_at: Optional[datetime] = None
    is_verified: Optional[bool] = None
    verified_by: Optional[uuid.UUID] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None
    retry_count: int
    timeout_count: int
    created_at: datetime
    updated_at: datetime

class VerificationEdit(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    field_name: str
    original_value: Optional[str]
    current_value: Optional[str]
    edited_by: uuid.UUID
    edited_at: datetime
    edit_reason: Optional[str]