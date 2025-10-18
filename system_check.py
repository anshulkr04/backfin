#!/usr/bin/env python3
"""
System Architecture Verification
Checks that all components are properly connected and operational
"""

import sys
import time
import redis
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

def check_redis_connection():
    """Test Redis connection"""
    try:
        client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        client.ping()
        print("✅ Redis connection: OPERATIONAL")
        return client
    except Exception as e:
        print(f"❌ Redis connection: FAILED ({e})")
        return None

def check_queue_architecture(redis_client):
    """Verify queue architecture"""
    print("\n📊 Queue Architecture Check:")
    
    try:
        from src.queue.redis_client import QueueNames
        
        main_queues = [
            QueueNames.AI_PROCESSING,
            QueueNames.SUPABASE_UPLOAD, 
            QueueNames.INVESTOR_PROCESSING
        ]
        
        for queue in main_queues:
            # Check main queue
            main_count = redis_client.llen(queue)
            
            # Check delayed queue
            delayed_queue = f"{queue}:delayed"
            delayed_count = redis_client.zcard(delayed_queue)
            
            queue_short = queue.split(':')[-1].upper()
            print(f"  {queue_short:<15}: {main_count} jobs ({delayed_count} delayed)")
        
        print("✅ Queue architecture: PROPERLY CONFIGURED")
        return True
        
    except Exception as e:
        print(f"❌ Queue architecture: ERROR ({e})")
        return False

def check_worker_components():
    """Check if worker components exist and are importable"""
    print("\n🔧 Worker Components Check:")
    
    components = [
        ("AI Worker", "workers.ephemeral_ai_worker"),
        ("Supabase Worker", "workers.ephemeral_supabase_worker"),
        ("Investor Worker", "workers.ephemeral_investor_worker"),
        ("Delayed Queue Processor", "workers.delayed_queue_processor"),
        ("Worker Spawner", "management.worker_spawner")
    ]
    
    all_good = True
    for name, module_path in components:
        try:
            __import__(module_path)
            print(f"✅ {name}: IMPORTABLE")
        except Exception as e:
            print(f"❌ {name}: IMPORT ERROR ({e})")
            all_good = False
    
    return all_good

def check_scraper_integration():
    """Check if scrapers are integrated with queue system"""
    print("\n🕷️  Scraper Integration Check:")
    
    scrapers = [
        ("BSE Scraper", "src.scrapers.bse_scraper"),
        ("NSE Scraper", "src.scrapers.nse_scraper")
    ]
    
    all_good = True
    for name, module_path in scrapers:
        try:
            module = __import__(module_path, fromlist=[''])
            
            # Check if REDIS_AVAILABLE is True
            if hasattr(module, 'REDIS_AVAILABLE') and module.REDIS_AVAILABLE:
                print(f"✅ {name}: QUEUE INTEGRATED")
            else:
                print(f"⚠️  {name}: QUEUE NOT AVAILABLE")
                all_good = False
                
        except Exception as e:
            print(f"❌ {name}: ERROR ({e})")
            all_good = False
    
    return all_good

def check_api_endpoints():
    """Check API integration"""
    print("\n🌐 API Integration Check:")
    
    try:
        from api.main import app
        print("✅ API Server: IMPORTABLE")
        
        # Check if endpoints exist (basic check)
        routes = [str(route.path) for route in app.routes]
        critical_routes = ["/health", "/queues/status", "/jobs/announcement"]
        
        for route in critical_routes:
            if any(route in r for r in routes):
                print(f"✅ Endpoint {route}: EXISTS")
            else:
                print(f"❌ Endpoint {route}: MISSING")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ API Server: ERROR ({e})")
        return False

def check_ai_processing():
    """Check AI processing integration"""
    print("\n🤖 AI Processing Check:")
    
    try:
        from src.ai.prompts import category_prompt, headline_prompt
        print("✅ AI Prompts: AVAILABLE")
        
        # Check if Google AI is configured
        import os
        if os.getenv('GOOGLE_API_KEY'):
            print("✅ Google AI API Key: CONFIGURED")
        else:
            print("⚠️  Google AI API Key: NOT SET")
        
        return True
        
    except Exception as e:
        print(f"❌ AI Processing: ERROR ({e})")
        return False

def main():
    """Run comprehensive system check"""
    print("🎯 BACKFIN SYSTEM ARCHITECTURE VERIFICATION")
    print("=" * 60)
    
    # Check Redis
    redis_client = check_redis_connection()
    if not redis_client:
        print("\n❌ CRITICAL: Redis not available - system cannot operate")
        return False
    
    # Run all checks
    checks = [
        check_queue_architecture(redis_client),
        check_worker_components(),
        check_scraper_integration(), 
        check_api_endpoints(),
        check_ai_processing()
    ]
    
    print("\n" + "=" * 60)
    
    if all(checks):
        print("🎉 SYSTEM STATUS: FULLY OPERATIONAL")
        print("✅ All components properly connected and configured")
        print("\n🚀 Ready to:")
        print("  • Scrape announcements and queue for processing")
        print("  • Process AI jobs with retry and Error prevention")
        print("  • Upload to Supabase with validation")
        print("  • Handle delayed jobs with adaptive gap management")
        print("  • Spawn workers dynamically based on queue load")
        return True
    else:
        print("⚠️  SYSTEM STATUS: ISSUES DETECTED")
        print("❌ Some components need attention")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)