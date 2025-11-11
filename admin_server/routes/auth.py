from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import HTMLResponse
from datetime import datetime, timedelta
import uuid

from models.auth import UserRegister, UserLogin, TokenResponse, UserResponse
from auth.jwt_handler import AuthService, get_current_user, get_current_user_optional
from services.supabase_client import supabase_service

router = APIRouter()

@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegister, request: Request):
    """Register a new admin user"""
    # Check if user already exists
    existing_user = await supabase_service.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Hash password
    password_hash = AuthService.hash_password(user_data.password)
    
    # Create user
    try:
        user = await supabase_service.create_user(
            email=user_data.email,
            password_hash=password_hash,
            name=user_data.name
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )
    
    # Create session
    session_token = AuthService.generate_session_token()
    expires_at = datetime.utcnow() + timedelta(hours=8)
    
    session = await supabase_service.create_session(
        user_id=str(user.id),
        session_token=session_token,
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host
    )
    
    # Create JWT tokens
    tokens = AuthService.create_token_pair(str(user.id), str(session.id))
    
    # Log activity
    await supabase_service.log_activity(
        user_id=str(user.id),
        session_id=str(session.id),
        action="register",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return TokenResponse(**tokens)

@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin, request: Request):
    """Login with email and password"""
    # Get user by email
    user = await supabase_service.get_user_by_email(user_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Verify password
    if not AuthService.verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Check if user is active and verified
    if not user.is_active or not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active or verified"
        )
    
    # Create session
    session_token = AuthService.generate_session_token()
    expires_at = datetime.utcnow() + timedelta(hours=8)
    
    session = await supabase_service.create_session(
        user_id=str(user.id),
        session_token=session_token,
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host
    )
    
    # Create JWT tokens
    tokens = AuthService.create_token_pair(str(user.id), str(session.id))
    
    # Log activity
    await supabase_service.log_activity(
        user_id=str(user.id),
        session_id=str(session.id),
        action="login",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return TokenResponse(**tokens)

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user), request: Request = None):
    """Logout and deactivate session"""
    user_id = current_user["user_id"]
    session_id = current_user["session_id"]
    
    # Deactivate session
    await supabase_service.deactivate_session(session_id)
    
    # Log activity
    await supabase_service.log_activity(
        user_id=user_id,
        session_id=session_id,
        action="logout",
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None
    )
    
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    user_id = current_user["user_id"]
    session_id = current_user["session_id"]
    
    # Update session activity
    await supabase_service.update_session_activity(session_id)
    
    # Get user details
    user = await supabase_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at
    )

# HTML registration form for easy testing
@router.get("/register", response_class=HTMLResponse)
async def register_form():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Registration</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; padding: 20px; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; width: 100%; }
            button:hover { background: #0056b3; }
            .error { color: red; margin-top: 10px; }
            .success { color: green; margin-top: 10px; }
        </style>
    </head>
    <body>
        <h2>🛡️ Admin Registration</h2>
        <form id="registerForm">
            <div class="form-group">
                <label for="name">Full Name:</label>
                <input type="text" id="name" name="name" required>
            </div>
            <div class="form-group">
                <label for="email">Email:</label>
                <input type="email" id="email" name="email" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Register</button>
        </form>
        <div id="message"></div>
        
        <p><a href="/auth/login">Already have an account? Login here</a></p>
        
        <script>
            document.getElementById('registerForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData(e.target);
                const data = {
                    name: formData.get('name'),
                    email: formData.get('email'),
                    password: formData.get('password')
                };
                
                try {
                    const response = await fetch('/auth/register', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        document.getElementById('message').innerHTML = 
                            '<div class="success">Registration successful! Access token: ' + result.access_token.substring(0, 20) + '...</div>';
                        localStorage.setItem('admin_token', result.access_token);
                        setTimeout(() => window.location.href = '/', 2000);
                    } else {
                        document.getElementById('message').innerHTML = 
                            '<div class="error">Error: ' + result.detail + '</div>';
                    }
                } catch (error) {
                    document.getElementById('message').innerHTML = 
                        '<div class="error">Network error: ' + error.message + '</div>';
                }
            });
        </script>
    </body>
    </html>
    """

# HTML login form for easy testing
@router.get("/login", response_class=HTMLResponse)
async def login_form():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Login</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; padding: 20px; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; width: 100%; }
            button:hover { background: #0056b3; }
            .error { color: red; margin-top: 10px; }
            .success { color: green; margin-top: 10px; }
        </style>
    </head>
    <body>
        <h2>🔐 Admin Login</h2>
        <form id="loginForm">
            <div class="form-group">
                <label for="email">Email:</label>
                <input type="email" id="email" name="email" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Login</button>
        </form>
        <div id="message"></div>
        
        <p><a href="/auth/register">Don't have an account? Register here</a></p>
        
        <script>
            document.getElementById('loginForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData(e.target);
                const data = {
                    email: formData.get('email'),
                    password: formData.get('password')
                };
                
                try {
                    const response = await fetch('/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        document.getElementById('message').innerHTML = 
                            '<div class="success">Login successful! Redirecting...</div>';
                        localStorage.setItem('admin_token', result.access_token);
                        setTimeout(() => window.location.href = '/', 2000);
                    } else {
                        document.getElementById('message').innerHTML = 
                            '<div class="error">Error: ' + result.detail + '</div>';
                    }
                } catch (error) {
                    document.getElementById('message').innerHTML = 
                        '<div class="error">Network error: ' + error.message + '</div>';
                }
            });
        </script>
    </body>
    </html>
    """