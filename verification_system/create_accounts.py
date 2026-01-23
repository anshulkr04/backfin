#!/usr/bin/env python3
"""
Script to create Admin and Verifier accounts for the verification system
Creates:
1. Admin Account: adminUtkarsh@screenalpha.com / Alph@Tool
2. Verifier Account: verifier@screenalpha.com / verifier@Alpha
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from database import get_db
from auth import get_password_hash

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Account details
ACCOUNTS = [
    {
        "email": "adminUtkarsh@screenalpha.com",
        "password": "Alph@Tool",
        "name": "Admin Utkarsh",
        "role": "admin"
    },
    {
        "email": "verifier@screenalpha.com",
        "password": "verifier@Alpha",
        "name": "Verifier",
        "role": "verifier"
    }
]


def create_account(supabase, email: str, password: str, name: str, role: str):
    """
    Create a user account in the admin_users table
    
    Args:
        supabase: Supabase client
        email: User email
        password: Plain text password (will be hashed)
        name: User name
        role: User role ('admin' or 'verifier')
    
    Returns:
        Created user data or None if failed
    """
    try:
        # Check if email already exists
        existing = supabase.table("admin_users").select("email").eq("email", email).execute()
        
        if existing.data and len(existing.data) > 0:
            logger.warning(f"⚠️  Email already exists: {email}")
            return None
        
        # Hash password
        password_hash = get_password_hash(password)
        
        # Create user data
        user_data = {
            "email": email,
            "password_hash": password_hash,
            "name": name,
            "is_active": True,
            "is_verified": True,
            "role": role
        }
        
        # Insert into database
        result = supabase.table("admin_users").insert(user_data).execute()
        
        if not result.data or len(result.data) == 0:
            logger.error(f"❌ Failed to create user: {email}")
            return None
        
        user = result.data[0]
        logger.info(f"✅ Created {role} account: {email} (ID: {user['id']})")
        return user
        
    except Exception as e:
        logger.error(f"❌ Error creating account {email}: {e}")
        return None


def main():
    """Main function to create accounts"""
    logger.info("=" * 60)
    logger.info("Creating Verification System Accounts")
    logger.info("=" * 60)
    
    try:
        # Get Supabase client
        supabase = get_db()
        logger.info("✅ Connected to Supabase")
        
        # Create accounts
        created_count = 0
        for account in ACCOUNTS:
            logger.info(f"\nCreating {account['role'].upper()} account...")
            logger.info(f"Email: {account['email']}")
            logger.info(f"Name: {account['name']}")
            
            user = create_account(
                supabase=supabase,
                email=account['email'],
                password=account['password'],
                name=account['name'],
                role=account['role']
            )
            
            if user:
                created_count += 1
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info(f"Account Creation Summary")
        logger.info("=" * 60)
        logger.info(f"Total accounts to create: {len(ACCOUNTS)}")
        logger.info(f"Successfully created: {created_count}")
        logger.info(f"Already existed/Failed: {len(ACCOUNTS) - created_count}")
        
        if created_count == len(ACCOUNTS):
            logger.info("\n✅ All accounts created successfully!")
        elif created_count > 0:
            logger.info("\n⚠️  Some accounts were created, but not all")
        else:
            logger.warning("\n❌ No accounts were created")
        
        # Display credentials
        logger.info("\n" + "=" * 60)
        logger.info("Account Credentials")
        logger.info("=" * 60)
        logger.info("\n1. ADMIN ACCOUNT:")
        logger.info(f"   Email: {ACCOUNTS[0]['email']}")
        logger.info(f"   Password: {ACCOUNTS[0]['password']}")
        logger.info(f"   Role: {ACCOUNTS[0]['role']}")
        
        logger.info("\n2. VERIFIER ACCOUNT:")
        logger.info(f"   Email: {ACCOUNTS[1]['email']}")
        logger.info(f"   Password: {ACCOUNTS[1]['password']}")
        logger.info(f"   Role: {ACCOUNTS[1]['role']}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
