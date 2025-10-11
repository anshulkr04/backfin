#!/usr/bin/env python3
"""
Test Ephemeral Worker Architecture
"""

import time
import sys
import uuid
import logging
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import *
import redis

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Test ephemeral workers"""
    print("🎯 TESTING EPHEMERAL WORKER ARCHITECTURE")
    print("=" * 60)
    
    # Setup Redis
    config = RedisConfig()
    r = redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        decode_responses=True
    )
    
    # Clear queues
    for queue_name in QueueNames.all_queues():
        r.delete(queue_name)
    print("🧹 Cleared all queues")
    
    # Add test jobs
    test_id = str(uuid.uuid4())[:8]
    
    print(f"\n📤 Adding test jobs (flow ID: {test_id})...")
    
    # Add AI job
    ai_job = AIProcessingJob(
        job_id=f"ephemeral_test_{test_id}_ai",
        corp_id=f"CORP_{test_id}",
        company_name="Ephemeral Test Company",
        security_id=f"TEST{test_id[:4]}"
    )
    r.lpush(QueueNames.AI_PROCESSING, serialize_job(ai_job))
    print("   ✅ Added AI processing job")
    
    # Add Supabase job
    supabase_job = SupabaseUploadJob(
        job_id=f"ephemeral_test_{test_id}_supabase",
        corp_id=f"CORP_{test_id}",
        processed_data={
            "summary": "Test announcement for ephemeral workers",
            "category": "test_category",
            "processed_at": datetime.now().isoformat()
        }
    )
    r.lpush(QueueNames.SUPABASE_UPLOAD, serialize_job(supabase_job))
    print("   ✅ Added Supabase upload job")
    
    # Add Investor job
    investor_job = InvestorAnalysisJob(
        job_id=f"ephemeral_test_{test_id}_investor",
        corp_id=f"CORP_{test_id}",
        category="test_category",
        individual_investors=["Test Investor 1", "Test Investor 2"],
        company_investors=["Test Company A"]
    )
    r.lpush(QueueNames.INVESTOR_PROCESSING, serialize_job(investor_job))
    print("   ✅ Added investor analysis job")
    
    # Show initial queue status
    print(f"\n📊 Initial queue status:")
    for queue_name in [QueueNames.AI_PROCESSING, QueueNames.SUPABASE_UPLOAD, QueueNames.INVESTOR_PROCESSING]:
        length = r.llen(queue_name)
        queue_short = queue_name.split(':')[-1].upper()
        print(f"   {queue_short}: {length} jobs")
    
    print(f"\n🎯 Jobs added! Now:")
    print("1. Start the worker spawner: python management/worker_spawner.py")
    print("2. Watch workers spawn automatically when jobs are detected")
    print("3. Workers will process jobs and shut down when done")
    print("4. Perfect for AWS Lambda/ECS where you pay per execution time!")
    
    print(f"\n💡 AWS Benefits:")
    print("   ✅ Workers only run when needed")
    print("   ✅ Auto-shutdown after processing")
    print("   ✅ No idle costs")
    print("   ✅ Event-driven scaling")
    print("   ✅ Cost-efficient for variable workloads")

if __name__ == "__main__":
    main()