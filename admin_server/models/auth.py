from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
import uuid

# Request models
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenRefresh(BaseModel):
    refresh_token: str

# Response models
class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    is_active: bool
    is_verified: bool
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class SessionResponse(BaseModel):
    id: str
    user_id: str
    expires_at: datetime
    last_activity: datetime

# Internal models
class AdminUser(BaseModel):
    id: uuid.UUID
    email: str
    password_hash: str
    name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

class AdminSession(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    session_token: str
    expires_at: datetime
    is_active: bool
    last_activity: datetime
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime