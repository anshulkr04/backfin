"""
Authentication utilities for Backfin Verification System
JWT token generation, password hashing, user verification
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr

from config import settings
from database import get_db

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()

# ============================================================================
# Models
# ============================================================================

class TokenData(BaseModel):
    """Data stored in JWT token"""
    email: EmailStr
    user_id: str
    role: str = "verifier"  # 'admin' or 'verifier'
    exp: Optional[datetime] = None

class AuthToken(BaseModel):
    """Response model for authentication"""
    access_token: str
    token_type: str
    user: dict

# ============================================================================
# Password Hashing
# ============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against hashed password using bcrypt directly
    
    Args:
        plain_password: Plain text password from user
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt directly
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    try:
        # Bcrypt has a 72-byte limit, truncate if necessary
        password_bytes = password.encode('utf-8')[:72]
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
    except Exception as e:
        logger.error(f"Password hashing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password hashing failed"
        )

# ============================================================================
# JWT Token Management
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: Dictionary of data to encode in token (must include 'sub' for email)
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> TokenData:
    """
    Decode and verify a JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        TokenData object with user information
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        email: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        role: str = payload.get("role", "verifier")
        exp: int = payload.get("exp")
        
        if email is None or user_id is None:
            raise credentials_exception
        
        # Convert exp timestamp to datetime
        exp_datetime = datetime.fromtimestamp(exp) if exp else None
        
        return TokenData(email=email, user_id=user_id, role=role, exp=exp_datetime)
        
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Token decode error: {e}")
        raise credentials_exception

# ============================================================================
# Authentication Dependencies
# ============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    supabase = Depends(get_db)
) -> TokenData:
    """
    FastAPI dependency to get current authenticated user
    Validates JWT token and checks if session is active in database
    
    Args:
        credentials: HTTP Bearer token from request header
        supabase: Supabase client from dependency injection
        
    Returns:
        TokenData with user information
        
    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    
    # Decode token
    token_data = decode_access_token(token)
    
    # Check if session exists and is active
    try:
        session_result = supabase.table("admin_sessions").select("*").eq(
            "session_token", token
        ).eq("is_active", True).execute()
        
        if not session_result.data or len(session_result.data) == 0:
            logger.error(f"No active session found for token. User ID from token: {token_data.user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired or invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        session = session_result.data[0]
        
        # Check session expiration
        from datetime import timezone
        expires_at_str = session["expires_at"].replace('Z', '+00:00')
        expires_at = datetime.fromisoformat(expires_at_str)
        now = datetime.now(timezone.utc)
        
        if expires_at < now:
            # Mark session as inactive
            supabase.table("admin_sessions").update({"is_active": False}).eq("id", session["id"]).execute()
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is still active
        user_result = supabase.table("admin_users").select("is_active").eq("id", token_data.user_id).execute()
        
        if not user_result.data or not user_result.data[0].get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated"
            )
        
        return token_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """
    Additional dependency layer if needed for more checks
    Currently just passes through from get_current_user
    """
    return current_user


# ============================================================================
# Role-Based Access Control
# ============================================================================

async def require_admin(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """
    FastAPI dependency that requires admin role
    Use this to protect admin-only endpoints like review queue
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        TokenData if user is admin
        
    Raises:
        HTTPException: If user is not an admin
    """
    if current_user.role != "admin":
        logger.warning(f"Access denied for user {current_user.email} (role: {current_user.role}) - admin required")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required. You do not have permission to access this resource."
        )
    return current_user


async def require_admin_or_verifier(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """
    FastAPI dependency that requires admin or verifier role
    Use this for endpoints accessible to both roles
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        TokenData if user has required role
        
    Raises:
        HTTPException: If user doesn't have valid role
    """
    if current_user.role not in ["admin", "verifier"]:
        logger.warning(f"Access denied for user {current_user.email} (role: {current_user.role})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return current_user
