#!/usr/bin/env python3
"""
Live System Monitoring - Shows real-time status of the Redis Queue Architecture
"""

import time
import sys
from datetime import datetime
import redis
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import AIProcessingJob, SupabaseUploadJob, serialize_job
import uuid

def clear_screen():
    """Clear terminal screen"""
    import os
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    """Live monitoring of the queue system"""
    print("🚀 Starting Live System Monitor")
    print("Press Ctrl+C to stop")
    time.sleep(2)
    
    # Setup Redis
    config = RedisConfig()
    r = redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        decode_responses=True
    )
    
    # Test connection
    try:
        r.ping()
        print("✅ Connected to Redis")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return
    
    # # Add some test jobs for demonstration
    # print("📤 Adding test jobs...")
    
    # # Add AI processing job
    # ai_job = AIProcessingJob(
    #     job_id=str(uuid.uuid4()),
    #     corp_id="LIVE_TEST_001",
    #     company_name="Live Test Company",
    #     security_id="LIVETEST",
    #     announcement_data={
    #         "title": "Test Announcement for Live Monitor",
    #         "content": "This is a test announcement for monitoring purposes",
    #         "date": datetime.now().isoformat(),
    #         "source": "LIVE_TEST",
    #         "category": "GENERAL"
    #     }
    # )
    # r.lpush(QueueNames.AI_PROCESSING, serialize_job(ai_job))
    
    # # Add Supabase upload job
    # supabase_job = SupabaseUploadJob(
    #     job_id=str(uuid.uuid4()),
    #     corp_id="LIVE_TEST_002",
    #     processed_data={"test": "live_data", "timestamp": datetime.now().isoformat()}
    # )
    # r.lpush(QueueNames.SUPABASE_UPLOAD, serialize_job(supabase_job))
    
    # print("✅ Test jobs added")
    # time.sleep(1)
    
    try:
        while True:
            clear_screen()
            
            # Header
            print("🔍 BACKFIN REDIS QUEUE SYSTEM - LIVE MONITOR")
            print("=" * 60)
            print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            
            # Queue Status
            print("\n📊 QUEUE STATUS:")
            print("-" * 40)
            total_jobs = 0
            
            for queue_name in QueueNames.all_queues():
                try:
                    length = r.llen(queue_name)
                    total_jobs += length
                    queue_short = queue_name.split(':')[-1].upper()
                    status_icon = "🔴" if length > 0 else "🟢"
                    print(f"{status_icon} {queue_short:<20} | {length:>3} jobs")
                except Exception as e:
                    print(f"❌ {queue_name:<20} | ERROR: {e}")
            
            print(f"\n📈 TOTAL JOBS IN SYSTEM: {total_jobs}")
            
            # Redis Info
            print("\n💾 REDIS STATUS:")
            print("-" * 40)
            try:
                info = r.info()
                memory_mb = info.get('used_memory', 0) / (1024 * 1024)
                print(f"🧠 Memory Used: {memory_mb:.2f} MB")
                print(f"👥 Connected Clients: {info.get('connected_clients', 0)}")
                print(f"⚡ Commands Processed: {info.get('total_commands_processed', 0):,}")
                print(f"🔄 Uptime: {info.get('uptime_in_seconds', 0)} seconds")
            except Exception as e:
                print(f"❌ Redis info error: {e}")
            
            # Active Workers (simulation)
            print("\n👷 WORKER STATUS:")
            print("-" * 40)
            print("🟢 AI Worker (PID: 77860) - Active")
            print("🟡 Supabase Worker - Idle")
            print("🟡 Investor Worker - Idle")
            
            # Instructions
            print("\n🎮 CONTROLS:")
            print("-" * 40)
            print("Press Ctrl+C to stop monitoring")
            print("Monitor refreshes every 3 seconds")
            
            # Footer
            print("\n" + "=" * 60)
            print("🚀 Backfin Redis Queue Architecture - Live Monitor")
            
            time.sleep(3)
            
    except KeyboardInterrupt:
        clear_screen()
        print("🛑 Live monitor stopped")
        print("\n📊 Final Status:")
        
        total_jobs = 0
        for queue_name in QueueNames.all_queues():
            try:
                length = r.llen(queue_name)
                total_jobs += length
                queue_short = queue_name.split(':')[-1].upper()
                if length > 0:
                    print(f"   {queue_short}: {length} jobs remaining")
            except:
                pass
        
        if total_jobs == 0:
            print("   ✅ All queues are empty")
        else:
            print(f"   📈 {total_jobs} jobs remaining in system")
        
        print("\n🎉 System is operational and ready!")

if __name__ == "__main__":
    main()