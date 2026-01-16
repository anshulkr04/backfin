#!/usr/bin/env python3
"""
Pre-flight check script for Backfin Daily Cron Manager
Validates that all dependencies and configurations are in place
"""

import os
import sys
from pathlib import Path

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

def check_item(name, status, message=""):
    if status:
        print(f"{GREEN}✅ {name}{RESET}")
        if message:
            print(f"   {message}")
    else:
        print(f"{RED}❌ {name}{RESET}")
        if message:
            print(f"   {message}")
    return status

def main():
    print_header("Backfin Cron Manager - Pre-flight Check")
    
    all_checks_passed = True
    
    # Check Python version
    print_header("1. Python Environment")
    python_version = sys.version_info
    python_ok = python_version.major == 3 and python_version.minor >= 8
    all_checks_passed &= check_item(
        "Python Version",
        python_ok,
        f"Python {python_version.major}.{python_version.minor}.{python_version.micro}" +
        ("" if python_ok else " (need 3.8+)")
    )
    
    # Check virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    venv_exists = Path('.venv').exists()
    all_checks_passed &= check_item(
        "Virtual Environment",
        venv_exists,
        "Activated" if in_venv else "Exists (activate with: source .venv/bin/activate)"
    )
    
    # Check dependencies
    print_header("2. Dependencies")
    
    dependencies = {
        'apscheduler': 'APScheduler',
        'dotenv': 'python-dotenv',
        'supabase': 'supabase-py',
        'pandas': 'pandas',
        'requests': 'requests',
        'selenium': 'selenium',
    }
    
    for module, name in dependencies.items():
        try:
            __import__(module)
            all_checks_passed &= check_item(name, True)
        except ImportError:
            all_checks_passed &= check_item(name, False, "Install with: pip install -r requirements.txt")
    
    # Check environment variables
    print_header("3. Environment Variables")
    
    env_vars = [
        'SUPABASE_URL2',
        'SUPABASE_KEY2',
        'RESEND_API_KEY'
    ]
    
    # Load .env file
    env_file = Path('.env')
    env_file_exists = env_file.exists()
    all_checks_passed &= check_item(".env file", env_file_exists)
    
    if env_file_exists:
        from dotenv import load_dotenv
        load_dotenv()
        
        for var in env_vars:
            value = os.getenv(var)
            all_checks_passed &= check_item(
                var,
                bool(value),
                f"Set ({len(value)} chars)" if value else "Not set in .env file"
            )
    
    # Check directory structure
    print_header("4. Directory Structure")
    
    required_dirs = [
        'logs/cron',
        'src/services/exchange_data/corporate_actions',
        'src/services/exchange_data/deals_management',
        'src/services/exchange_data/insider_trading',
        'scripts',
    ]
    
    for dir_path in required_dirs:
        exists = Path(dir_path).exists()
        all_checks_passed &= check_item(dir_path, exists)
    
    # Check required files
    print_header("5. Required Files")
    
    required_files = [
        'daily_cron_manager.py',
        'src/services/exchange_data/corporate_actions/corporate_actions_collector.py',
        'src/services/exchange_data/deals_management/deals_detector.py',
        'src/services/exchange_data/insider_trading/insider_trading_detector.py',
        'scripts/send_daily_digest.py',
    ]
    
    for file_path in required_files:
        exists = Path(file_path).exists()
        all_checks_passed &= check_item(file_path, exists)
    
    # Check permissions
    print_header("6. File Permissions")
    
    executable_files = [
        'daily_cron_manager.py',
        'setup_cron.sh',
        'manage_cron.sh',
    ]
    
    for file_path in executable_files:
        path = Path(file_path)
        if path.exists():
            is_executable = os.access(path, os.X_OK)
            check_item(
                f"{file_path} executable",
                is_executable,
                "" if is_executable else f"Run: chmod +x {file_path}"
            )
    
    # Summary
    print_header("Summary")
    
    if all_checks_passed:
        print(f"{GREEN}✅ All checks passed! You're ready to run the cron manager.{RESET}")
        print(f"\nNext steps:")
        print(f"  1. Test jobs: python3 daily_cron_manager.py --test corporate_actions")
        print(f"  2. Start: ./manage_cron.sh start")
        print(f"  3. Monitor: ./manage_cron.sh status")
        return 0
    else:
        print(f"{RED}❌ Some checks failed. Please fix the issues above.{RESET}")
        print(f"\nCommon fixes:")
        print(f"  - Install dependencies: pip install -r requirements.txt")
        print(f"  - Create .env file with required variables")
        print(f"  - Make scripts executable: chmod +x *.sh daily_cron_manager.py")
        return 1

if __name__ == "__main__":
    sys.exit(main())
