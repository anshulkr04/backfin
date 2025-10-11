#!/usr/bin/env python3
"""
Test script to add a sample job to the queue system
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def test_redis_connection():
    """Test Redis connection"""
    try:
        from src.queue.redis_client import redis_client
        redis_client.ping()
        print("✅ Redis connection successful")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("💡 Make sure Redis is running: redis-server")
        return False

def test_queue_operations():
    """Test basic queue operations"""
    try:
        from src.queue.redis_client import redis_client, QueueNames
        from src.queue.job_types import AIProcessingJob, serialize_job
        
        # Create a test job
        test_job = AIProcessingJob(
            job_id=f"test_{int(time.time())}",
            corp_id="test-corp-123",
            pdf_url="test.pdf",
            company_name="Test Company",
            security_id="TEST001"
        )
        
        # Add job to queue
        redis_client.lpush(QueueNames.AI_PROCESSING, serialize_job(test_job))
        print("✅ Job added to queue successfully")
        
        # Check queue length
        queue_length = redis_client.llen(QueueNames.AI_PROCESSING)
        print(f"✅ Queue length: {queue_length}")
        
        # Remove the test job
        redis_client.rpop(QueueNames.AI_PROCESSING)
        print("✅ Test job removed from queue")
        
        return True
        
    except Exception as e:
        print(f"❌ Queue operations failed: {e}")
        return False

def test_job_serialization():
    """Test job serialization/deserialization"""
    try:
        from src.queue.job_types import AIProcessingJob, serialize_job, deserialize_job
        
        # Create test job
        original_job = AIProcessingJob(
            job_id="test_serialization",
            corp_id="test-corp-456", 
            company_name="Serialization Test Co"
        )
        
        # Serialize
        serialized = serialize_job(original_job)
        print("✅ Job serialization successful")
        
        # Deserialize
        deserialized_job = deserialize_job(serialized)
        print("✅ Job deserialization successful")
        
        # Verify data integrity
        if original_job.job_id == deserialized_job.job_id:
            print("✅ Data integrity verified")
            return True
        else:
            print("❌ Data integrity check failed")
            return False
            
    except Exception as e:
        print(f"❌ Job serialization test failed: {e}")
        return False

def test_queue_monitoring():
    """Test queue monitoring tools"""
    try:
        from management.queue_manager import QueueManager
        
        manager = QueueManager()
        lengths = manager.get_queue_lengths()
        
        print("✅ Queue monitoring working")
        print("📊 Current queue lengths:")
        for queue_name, length in lengths.items():
            queue_short = queue_name.split(':')[-1]
            print(f"   {queue_short}: {length}")
        
        return True
        
    except Exception as e:
        print(f"❌ Queue monitoring failed: {e}")
        return False

def main():
    """Run all queue system tests"""
    print("=" * 60)
    print("TESTING REDIS QUEUE SYSTEM")
    print("=" * 60)
    
    tests = [
        ("Redis Connection", test_redis_connection),
        ("Job Serialization", test_job_serialization),
        ("Queue Operations", test_queue_operations),
        ("Queue Monitoring", test_queue_monitoring),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\\n🧪 Testing {test_name}...")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:.<30} {status}")
    
    print(f"\\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\\n🎉 Queue system is fully functional!")
        print("💡 Next: Try running workers with 'python3 workers/start_ai_worker.py'")
    else:
        print("\\n⚠️  Some tests failed - check Redis installation and dependencies")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)