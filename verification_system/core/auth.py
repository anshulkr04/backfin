#!/usr/bin/env python3
"""
Admin authentication system with JWT sessions
"""

import os
import jwt
import bcrypt
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from core.database import DatabaseManager, AdminUser, AdminSession

logger = logging.getLogger(__name__)

@dataclass
class AuthResult:
    success: bool
    user: Optional[AdminUser] = None
    session: Optional[AdminSession] = None
    token: Optional[str] = None
    error: Optional[str] = None

class AdminAuthManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.jwt_secret = os.getenv('ADMIN_JWT_SECRET')
        self.jwt_algorithm = 'HS256'
        self.session_expire_hours = int(os.getenv('ADMIN_SESSION_EXPIRE_HOURS', '8'))
        
        if not self.jwt_secret:
            raise ValueError("ADMIN_JWT_SECRET environment variable is required")
        
        if len(self.jwt_secret) < 32:
            logger.warning("⚠️ JWT secret should be at least 32 characters for security")

    # ============================================================================
    # Password Management
    # ============================================================================
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against its hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            logger.error(f"❌ Error verifying password: {e}")
            return False

    # ============================================================================
    # User Registration
    # ============================================================================
    
    async def register_admin_user(
        self,
        email: str,
        password: str,
        name: str,
        require_verification: bool = True
    ) -> AuthResult:
        """Register a new admin user"""
        try:
            # Check if user already exists
            existing_user = await self.db.get_admin_user_by_email(email)
            if existing_user:
                return AuthResult(success=False, error="User with this email already exists")
            
            # Hash password
            password_hash = self.hash_password(password)
            
            # Create user
            user = await self.db.create_admin_user(
                email=email,
                password_hash=password_hash,
                name=name
            )
            
            logger.info(f"✅ Created admin user: {email}")
            
            return AuthResult(success=True, user=user)
            
        except Exception as e:
            logger.error(f"❌ Error registering admin user: {e}")
            return AuthResult(success=False, error="Failed to register user")

    # ============================================================================
    # Authentication
    # ============================================================================
    
    async def authenticate_user(
        self,
        email: str,
        password: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> AuthResult:
        """Authenticate user with email/password and create session"""
        try:
            # Get user by email
            user = await self.db.get_admin_user_by_email(email)
            if not user:
                logger.warning(f"⚠️ Login attempt with non-existent email: {email}")
                return AuthResult(success=False, error="Invalid email or password")
            
            # Check if user is active
            if not user.is_active:
                logger.warning(f"⚠️ Login attempt with inactive user: {email}")
                return AuthResult(success=False, error="Account is inactive")
            
            # Verify password
            if not self.verify_password(password, user.password_hash):
                logger.warning(f"⚠️ Invalid password for user: {email}")
                
                # Log failed login attempt
                await self.db.log_admin_activity(
                    user_id=user.id,
                    session_id=None,
                    action="login_failed",
                    details={"reason": "invalid_password", "email": email},
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                return AuthResult(success=False, error="Invalid email or password")
            
            # Create session
            session_result = await self.create_user_session(
                user=user,
                user_agent=user_agent,
                ip_address=ip_address
            )
            
            if not session_result.success:
                return session_result
            
            # Log successful login
            await self.db.log_admin_activity(
                user_id=user.id,
                session_id=session_result.session.id,
                action="login_success",
                details={"email": email},
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            logger.info(f"✅ Successful login: {email}")
            
            return AuthResult(
                success=True,
                user=user,
                session=session_result.session,
                token=session_result.token
            )
            
        except Exception as e:
            logger.error(f"❌ Error authenticating user: {e}")
            return AuthResult(success=False, error="Authentication failed")

    async def create_user_session(
        self,
        user: AdminUser,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> AuthResult:
        """Create a new session for authenticated user"""
        try:
            # Generate session token
            session_token = self.generate_session_token()
            expires_at = datetime.utcnow() + timedelta(hours=self.session_expire_hours)
            
            # Create session in database
            session = await self.db.create_admin_session(
                user_id=user.id,
                session_token=session_token,
                expires_at=expires_at,
                user_agent=user_agent,
                ip_address=ip_address
            )
            
            # Generate JWT token
            jwt_token = self.create_jwt_token(session.id, user.id, expires_at)
            
            return AuthResult(
                success=True,
                session=session,
                token=jwt_token
            )
            
        except Exception as e:
            logger.error(f"❌ Error creating user session: {e}")
            return AuthResult(success=False, error="Failed to create session")

    def generate_session_token(self) -> str:
        """Generate a secure session token"""
        return secrets.token_urlsafe(64)

    def create_jwt_token(self, session_id: str, user_id: str, expires_at: datetime) -> str:
        """Create JWT token with session information"""
        payload = {
            'session_id': session_id,
            'user_id': user_id,
            'exp': expires_at,
            'iat': datetime.utcnow(),
            'type': 'admin_session'
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

    # ============================================================================
    # Session Validation
    # ============================================================================
    
    async def validate_session(self, token: str) -> AuthResult:
        """Validate JWT token and return session info"""
        try:
            # Decode JWT
            try:
                payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            except jwt.ExpiredSignatureError:
                return AuthResult(success=False, error="Token expired")
            except jwt.InvalidTokenError:
                return AuthResult(success=False, error="Invalid token")
            
            session_id = payload.get('session_id')
            if not session_id:
                return AuthResult(success=False, error="Invalid token format")
            
            # Get session from database
            session = await self.db.get_admin_session(session_id)
            if not session:
                return AuthResult(success=False, error="Session not found")
            
            # Get user
            user = await self.db.get_admin_user_by_id(session.user_id)
            if not user or not user.is_active:
                return AuthResult(success=False, error="User not found or inactive")
            
            # Update session activity
            await self.db.update_session_activity(session.session_token)
            
            return AuthResult(
                success=True,
                user=user,
                session=session,
                token=token
            )
            
        except Exception as e:
            logger.error(f"❌ Error validating session: {e}")
            return AuthResult(success=False, error="Session validation failed")

    async def refresh_session(self, token: str) -> AuthResult:
        """Refresh an existing session"""
        try:
            # Validate current session
            validation = await self.validate_session(token)
            if not validation.success:
                return validation
            
            # Check if session needs refresh (more than half expired)
            session = validation.session
            now = datetime.utcnow()
            time_until_expiry = session.expires_at - now
            session_duration = timedelta(hours=self.session_expire_hours)
            
            if time_until_expiry < session_duration / 2:
                # Create new session
                return await self.create_user_session(
                    user=validation.user,
                    user_agent=session.user_agent,
                    ip_address=session.ip_address
                )
            
            # Session is still fresh
            return validation
            
        except Exception as e:
            logger.error(f"❌ Error refreshing session: {e}")
            return AuthResult(success=False, error="Session refresh failed")

    # ============================================================================
    # Session Management
    # ============================================================================
    
    async def logout_user(
        self,
        token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> bool:
        """Logout user by expiring their session"""
        try:
            # Validate session first
            validation = await self.validate_session(token)
            if not validation.success:
                return False
            
            # Expire session
            success = await self.db.expire_admin_session(validation.session.session_token)
            
            if success:
                # Log logout
                await self.db.log_admin_activity(
                    user_id=validation.user.id,
                    session_id=validation.session.id,
                    action="logout",
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                logger.info(f"✅ User logged out: {validation.user.email}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error logging out user: {e}")
            return False

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        try:
            return await self.db.cleanup_expired_sessions()
        except Exception as e:
            logger.error(f"❌ Error cleaning up expired sessions: {e}")
            return 0

    # ============================================================================
    # Middleware Helpers
    # ============================================================================
    
    def extract_token_from_header(self, authorization: Optional[str]) -> Optional[str]:
        """Extract JWT token from Authorization header"""
        if not authorization:
            return None
        
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None
        
        return parts[1]

    async def get_current_user(self, authorization: Optional[str]) -> Tuple[Optional[AdminUser], Optional[AdminSession]]:
        """Get current user from Authorization header"""
        token = self.extract_token_from_header(authorization)
        if not token:
            return None, None
        
        validation = await self.validate_session(token)
        if not validation.success:
            return None, None
        
        return validation.user, validation.session

    # ============================================================================
    # Utility Methods
    # ============================================================================
    
    def validate_password_strength(self, password: str) -> Tuple[bool, str]:
        """Validate password strength"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password)
        
        if not (has_upper and has_lower and has_digit):
            return False, "Password must contain uppercase, lowercase, and numeric characters"
        
        return True, "Password is strong"

    def validate_email_format(self, email: str) -> bool:
        """Basic email format validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None