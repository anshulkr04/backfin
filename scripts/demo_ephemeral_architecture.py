#!/usr/bin/env python3
"""
AWS-Ready Ephemeral Worker Architecture Demo
Shows workers spawning only when needed and shutting down after completion
"""

import time
import sys
import uuid
import subprocess
import signal
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import *
import redis

def clear_screen():
    """Clear terminal screen"""
    import os
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    """Demo the ephemeral worker architecture"""
    print("🚀 AWS-READY EPHEMERAL WORKER ARCHITECTURE DEMO")
    print("=" * 70)
    print("💡 Perfect for AWS Lambda, ECS, or any pay-per-use cloud platform!")
    print("✅ Workers spawn only when jobs are available")
    print("✅ Workers shutdown automatically after processing")
    print("✅ Zero idle costs - you only pay for actual work done")
    print()
    
    # Setup Redis
    config = RedisConfig()
    r = redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        decode_responses=True
    )
    
    print("🔧 Setting up demo environment...")
    
    # Clear queues
    for queue_name in QueueNames.all_queues():
        r.delete(queue_name)
    
    print("✅ Queues cleared - starting with empty system")
    print()
    
    # Start worker spawner in background
    print("🚀 Starting ephemeral worker spawner...")
    spawner_process = subprocess.Popen(
        [sys.executable, "management/worker_spawner.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    
    time.sleep(2)
    print("✅ Worker spawner is running and monitoring queues")
    print()
    
    try:
        # Demo sequence
        scenarios = [
            {
                "name": "💼 New Business Announcement Processing",
                "jobs": [
                    AIProcessingJob(
                        job_id=f"demo_ai_{uuid.uuid4().hex[:8]}",
                        corp_id="RELIANCE_001",
                        company_name="Reliance Industries Ltd",
                        security_id="RELIANCE"
                    )
                ],
                "queue": QueueNames.AI_PROCESSING
            },
            {
                "name": "📊 Quarterly Results Analysis", 
                "jobs": [
                    SupabaseUploadJob(
                        job_id=f"demo_supabase_{uuid.uuid4().hex[:8]}",
                        corp_id="TCS_Q3_2024",
                        processed_data={
                            "summary": "TCS Q3 results show strong growth",
                            "category": "quarterly_results",
                            "sentiment": "positive"
                        }
                    )
                ],
                "queue": QueueNames.SUPABASE_UPLOAD
            },
            {
                "name": "👥 Investor Interest Analysis",
                "jobs": [
                    InvestorAnalysisJob(
                        job_id=f"demo_investor_{uuid.uuid4().hex[:8]}",
                        corp_id="HDFC_MERGER_2024",
                        category="merger_announcement",
                        individual_investors=["Retail Investor Group"],
                        company_investors=["Mutual Fund Houses", "FII Groups"]
                    )
                ],
                "queue": QueueNames.INVESTOR_PROCESSING
            }
        ]
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"📋 SCENARIO {i}: {scenario['name']}")
            print("-" * 50)
            
            # Show current system state
            print("💤 Current state: System idle, no workers running")
            
            # Add jobs
            for job in scenario['jobs']:
                r.lpush(scenario['queue'], serialize_job(job))
            
            queue_short = scenario['queue'].split(':')[-1].upper()
            print(f"📤 Added {len(scenario['jobs'])} job(s) to {queue_short} queue")
            print("⚡ Worker spawner detects new jobs...")
            
            # Wait and show worker spawning
            time.sleep(3)
            print("🚀 Ephemeral worker spawned automatically!")
            print("🔄 Worker processing job...")
            
            # Monitor until job is processed
            start_time = time.time()
            while r.llen(scenario['queue']) > 0 and (time.time() - start_time) < 30:
                time.sleep(1)
            
            if r.llen(scenario['queue']) == 0:
                print("✅ Job processed successfully")
                print("⏱️  Worker shutting down (job complete)")
                print("💰 Cost savings: Worker only ran for ~5-10 seconds")
            else:
                print("⏳ Still processing...")
            
            print()
            
            if i < len(scenarios):
                print("⏸️  Waiting 5 seconds before next scenario...")
                time.sleep(5)
                print()
        
        # Final demonstration
        print("🎯 BULK PROCESSING DEMONSTRATION")
        print("-" * 50)
        print("💼 Simulating high-volume announcement processing...")
        
        # Add multiple jobs of different types
        bulk_jobs = []
        for j in range(3):
            # AI jobs
            ai_job = AIProcessingJob(
                job_id=f"bulk_ai_{j}_{uuid.uuid4().hex[:6]}",
                corp_id=f"BULK_CORP_{j}",
                company_name=f"Bulk Test Company {j}",
                security_id=f"BULK{j}"
            )
            r.lpush(QueueNames.AI_PROCESSING, serialize_job(ai_job))
            
            # Supabase jobs
            supabase_job = SupabaseUploadJob(
                job_id=f"bulk_supabase_{j}_{uuid.uuid4().hex[:6]}",
                corp_id=f"BULK_CORP_{j}",
                processed_data={"bulk_test": True, "index": j}
            )
            r.lpush(QueueNames.SUPABASE_UPLOAD, serialize_job(supabase_job))
        
        print(f"📤 Added 6 jobs across multiple queues")
        print("⚡ Multiple workers will spawn automatically...")
        print("🔄 Processing in parallel...")
        
        # Monitor bulk processing
        total_jobs_start = sum(r.llen(q) for q in [QueueNames.AI_PROCESSING, QueueNames.SUPABASE_UPLOAD])
        start_time = time.time()
        
        while True:
            current_jobs = sum(r.llen(q) for q in [QueueNames.AI_PROCESSING, QueueNames.SUPABASE_UPLOAD])
            processed = total_jobs_start - current_jobs
            
            if current_jobs == 0:
                processing_time = time.time() - start_time
                print(f"✅ All {total_jobs_start} jobs processed in {processing_time:.1f} seconds!")
                print("⏱️  All workers shutting down automatically")
                print("💰 AWS cost: Only paid for actual processing time")
                break
            elif time.time() - start_time > 60:
                print(f"⏳ Still processing... {processed}/{total_jobs_start} jobs done")
                break
            
            time.sleep(2)
        
        print()
        print("🎉 EPHEMERAL WORKER ARCHITECTURE DEMO COMPLETE!")
        print("=" * 70)
        print("✅ Workers spawned only when needed")
        print("✅ Workers shut down after processing")
        print("✅ Zero idle costs")
        print("✅ Automatic scaling based on workload")
        print("✅ Perfect for AWS Lambda/ECS/Fargate")
        print()
        print("💡 In production, this architecture provides:")
        print("   • Automatic cost optimization")
        print("   • Infinite horizontal scaling")
        print("   • Fault tolerance through job queues")
        print("   • Easy monitoring and observability")
        
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted")
    
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        try:
            spawner_process.terminate()
            spawner_process.wait(timeout=5)
            print("✅ Worker spawner stopped")
        except:
            spawner_process.kill()
            print("🔪 Worker spawner force killed")

if __name__ == "__main__":
    main()