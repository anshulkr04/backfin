#!/usr/bin/env python3
"""
Test script to validate admin server setup without breaking existing system
"""

import sys
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables from parent directory
load_dotenv('/Users/anshulkumar/backfin/.env')

# Add admin_server to path
sys.path.insert(0, '/Users/anshulkumar/backfin/admin_server')

async def test_imports():
    """Test that all modules can be imported"""
    print("🧪 Testing admin server imports...")
    
    try:
        from models.auth import UserRegister, UserLogin, AdminUser
        print("✅ Auth models imported successfully")
        
        from models.verification import TaskResponse, VerificationTask
        print("✅ Verification models imported successfully")
        
        from services.supabase_client import SupabaseService
        print("✅ Supabase service imported successfully")
        
        from services.task_manager import TaskManager
        print("✅ Task manager imported successfully")
        
        from services.websocket_manager import WebSocketManager
        print("✅ WebSocket manager imported successfully")
        
        from services.reclaim_service import ReclaimService
        print("✅ Reclaim service imported successfully")
        
        from routes.auth import router as auth_router
        print("✅ Auth routes imported successfully")
        
        from routes.tasks import router as tasks_router
        print("✅ Task routes imported successfully")
        
        from routes.admin import router as admin_router
        print("✅ Admin routes imported successfully")
        
        print("🎉 All imports successful!")
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

async def test_environment():
    """Test environment variables"""
    print("\n🧪 Testing environment variables...")
    
    required_vars = [
        "SUPABASE_URL2",
        "SUPABASE_KEY2"
    ]
    
    optional_vars = [
        "REDIS_URL",
        "ADMIN_JWT_SECRET",
        "ADMIN_PORT"
    ]
    
    all_good = True
    
    for var in required_vars:
        if os.getenv(var):
            print(f"✅ {var} is set")
        else:
            print(f"❌ {var} is missing (required)")
            all_good = False
    
    for var in optional_vars:
        if os.getenv(var):
            print(f"✅ {var} is set")
        else:
            print(f"⚠️ {var} is missing (will use default)")
    
    return all_good

async def test_dependencies():
    """Test that required dependencies are available"""
    print("\n🧪 Testing dependencies...")
    
    required_packages = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "uvicorn"),
        ("supabase", "supabase client"),
        ("redis", "redis"),
        ("pydantic", "pydantic"),
        ("passlib", "password hashing"),
        ("multipart", "form handling"),
        ("jose", "JWT handling"),
        ("websockets", "WebSocket support")
    ]
    
    all_good = True
    
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"✅ {description} ({package}) available")
        except ImportError:
            print(f"❌ {description} ({package}) missing")
            all_good = False
    
    return all_good

async def main():
    """Run all tests"""
    print("🛡️ Admin Server Validation Tests")
    print("=" * 40)
    
    tests = [
        test_environment(),
        test_dependencies(),
        test_imports()
    ]
    
    results = await asyncio.gather(*tests, return_exceptions=True)
    
    success_count = sum(1 for r in results if r is True)
    total_count = len(results)
    
    print(f"\n📊 Test Results: {success_count}/{total_count} passed")
    
    if success_count == total_count:
        print("🎉 All tests passed! Admin server is ready to start.")
        print("\nTo start the admin server:")
        print("  cd /Users/anshulkumar/backfin/admin_server")
        print("  /Users/anshulkumar/backfin/.venv/bin/python main.py")
        return True
    else:
        print("❌ Some tests failed. Please fix the issues before starting the server.")
        return False

if __name__ == "__main__":
    asyncio.run(main())