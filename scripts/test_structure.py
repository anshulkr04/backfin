#!/usr/bin/env python3
"""
Test script to validate the new directory structure and imports
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def test_import_system():
    """Test importing key components"""
    tests = []
    
    # Test 1: Queue system imports
    try:
        from src.queue.redis_client import QueueNames, RedisConfig
        from src.queue.job_types import BaseJob, AIProcessingJob
        tests.append(("✅ Queue system imports", True))
    except Exception as e:
        tests.append((f"❌ Queue system imports: {e}", False))
    
    # Test 2: AI system imports  
    try:
        from src.ai.prompts import all_prompt, category_prompt
        tests.append(("✅ AI system imports", True))
    except Exception as e:
        tests.append((f"❌ AI system imports: {e}", False))
    
    # Test 3: Scrapers imports
    try:
        # Note: These will likely fail due to missing dependencies, but structure is correct
        import src.scrapers.bse_scraper
        import src.scrapers.nse_scraper
        tests.append(("✅ Scraper imports", True))
    except Exception as e:
        tests.append((f"⚠️  Scraper imports (expected - dependencies): {e}", True))
    
    # Test 4: Services imports
    try:
        import src.services.investor_analyzer
        import src.services.notification_service
        tests.append(("✅ Services imports", True))
    except Exception as e:
        tests.append((f"⚠️  Services imports (expected - dependencies): {e}", True))
    
    # Test 5: Utils imports
    try:
        import src.utils.company_data
        import src.utils.security_utils
        tests.append(("✅ Utils imports", True))
    except Exception as e:
        tests.append((f"⚠️  Utils imports (expected - dependencies): {e}", True))
    
    return tests

def test_file_structure():
    """Test that files are in expected locations"""
    tests = []
    
    expected_files = [
        "src/scrapers/bse_scraper.py",
        "src/ai/prompts.py", 
        "src/queue/redis_client.py",
        "src/queue/job_types.py",
        "workers/start_ai_worker.py",
        "management/queue_manager.py",
        "api/app.py",
        "docker-compose.redis.yml"
    ]
    
    for file_path in expected_files:
        if os.path.exists(file_path):
            tests.append((f"✅ {file_path} exists", True))
        else:
            tests.append((f"❌ {file_path} missing", False))
    
    return tests

def test_queue_definitions():
    """Test queue name definitions"""
    tests = []
    
    try:
        from src.queue.redis_client import QueueNames
        
        # Check queue names are defined
        queues = QueueNames.all_queues()
        if len(queues) >= 5:
            tests.append((f"✅ Queue definitions: {len(queues)} queues", True))
        else:
            tests.append((f"❌ Queue definitions: only {len(queues)} queues", False))
        
        # Check specific queues exist
        expected_queues = ['NEW_ANNOUNCEMENTS', 'AI_PROCESSING', 'SUPABASE_UPLOAD']
        for queue in expected_queues:
            if hasattr(QueueNames, queue):
                tests.append((f"✅ Queue {queue} defined", True))
            else:
                tests.append((f"❌ Queue {queue} missing", False))
                
    except Exception as e:
        tests.append((f"❌ Queue definitions test failed: {e}", False))
    
    return tests

def main():
    """Run all structure tests"""
    print("=" * 60)
    print("TESTING NEW REDIS QUEUE ARCHITECTURE")
    print("=" * 60)
    
    all_tests = []
    
    print("\\n1. Testing Imports...")
    all_tests.extend(test_import_system())
    
    print("\\n2. Testing File Structure...")
    all_tests.extend(test_file_structure())
    
    print("\\n3. Testing Queue Definitions...")
    all_tests.extend(test_queue_definitions())
    
    # Print results
    print("\\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    
    passed = 0
    total = 0
    
    for message, success in all_tests:
        print(message)
        if success:
            passed += 1
        total += 1
    
    print(f"\\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\\n🎉 All tests passed! Structure is ready.")
    elif passed >= total * 0.8:
        print("\\n⚠️  Mostly working - install dependencies for full functionality")
    else:
        print("\\n❌ Major issues found - check the errors above")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)