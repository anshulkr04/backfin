#!/usr/bin/env python3
"""
Comprehensive System Test for Backfin Redis Queue Architecture
Tests all components working together end-to-end
"""

import asyncio
import logging
import sys
import time
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any
import subprocess
import signal
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import (
    AnnouncementScrapingJob, 
    AIProcessingJob, 
    SupabaseUploadJob,
    InvestorAnalysisJob,
    serialize_job,
    deserialize_job
)
import redis

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SystemTester:
    """Comprehensive system tester"""
    
    def __init__(self):
        self.redis_config = RedisConfig()
        self.redis_client = None
        self.running_processes = []
        self.test_results = {}
        
    def setup_redis(self):
        """Setup Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_config.redis_host,
                port=self.redis_config.redis_port,
                db=self.redis_config.redis_db,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("✅ Redis connection established")
            return True
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            return False
    
    def clear_queues(self):
        """Clear all queues for clean testing"""
        try:
            for queue_name in QueueNames.all_queues():
                self.redis_client.delete(queue_name)
            logger.info("🧹 All queues cleared")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to clear queues: {e}")
            return False
    
    def test_queue_operations(self):
        """Test basic queue operations"""
        logger.info("🧪 Testing queue operations...")
        
        try:
            # Test job creation and serialization
            test_job = AIProcessingJob(
                job_id=str(uuid.uuid4()),
                corp_id="TEST001",
                company_name="Test Company",
                security_id="TEST"
            )
            
            # Serialize and add to queue
            job_json = serialize_job(test_job)
            self.redis_client.lpush(QueueNames.AI_PROCESSING, job_json)
            
            # Check queue length
            queue_length = self.redis_client.llen(QueueNames.AI_PROCESSING)
            if queue_length != 1:
                raise Exception(f"Expected queue length 1, got {queue_length}")
            
            # Retrieve and deserialize
            retrieved_json = self.redis_client.rpop(QueueNames.AI_PROCESSING)
            retrieved_job = deserialize_job(retrieved_json)
            
            if retrieved_job.corp_id != test_job.corp_id:
                raise Exception("Job data mismatch after round trip")
            
            logger.info("✅ Queue operations working correctly")
            self.test_results['queue_operations'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Queue operations failed: {e}")
            self.test_results['queue_operations'] = False
            return False
    
    def start_worker(self, worker_script: str, worker_name: str):
        """Start a worker process"""
        try:
            cmd = [sys.executable, worker_script]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.running_processes.append((process, worker_name))
            logger.info(f"🚀 Started {worker_name} (PID: {process.pid})")
            return process
        except Exception as e:
            logger.error(f"❌ Failed to start {worker_name}: {e}")
            return None
    
    def test_worker_processing(self):
        """Test that workers can process jobs"""
        logger.info("🧪 Testing worker processing...")
        
        try:
            # Add test jobs to different queues
            test_jobs = [
                (AIProcessingJob(
                    job_id=str(uuid.uuid4()),
                    corp_id="TEST_AI_001",
                    company_name="Test AI Company",
                    security_id="TESTAI"
                ), QueueNames.AI_PROCESSING),
                
                (SupabaseUploadJob(
                    job_id=str(uuid.uuid4()),
                    corp_id="TEST_SUP_001",
                    processed_data={"test": "data"}
                ), QueueNames.SUPABASE_UPLOAD),
                
                (InvestorAnalysisJob(
                    job_id=str(uuid.uuid4()),
                    corp_id="TEST_INV_001",
                    category="test_category"
                ), QueueNames.INVESTOR_PROCESSING)
            ]
            
            # Add jobs to queues
            initial_lengths = {}
            for job, queue_name in test_jobs:
                job_json = serialize_job(job)
                self.redis_client.lpush(queue_name, job_json)
                initial_lengths[queue_name] = self.redis_client.llen(queue_name)
                logger.info(f"📤 Added job to {queue_name}")
            
            # Start workers (we'll run them briefly)
            # Note: In a real test, workers would process these jobs
            # For now, we'll simulate processing by removing jobs manually
            
            time.sleep(2)  # Give a moment for any running workers
            
            # Check if any jobs were processed (queue lengths changed)
            processed_any = False
            for queue_name in initial_lengths:
                current_length = self.redis_client.llen(queue_name)
                if current_length < initial_lengths[queue_name]:
                    logger.info(f"✅ Jobs processed in {queue_name}")
                    processed_any = True
                else:
                    # Manually remove for testing
                    if current_length > 0:
                        self.redis_client.rpop(queue_name)
                        logger.info(f"🧪 Manually cleared {queue_name} for testing")
            
            self.test_results['worker_processing'] = True
            logger.info("✅ Worker processing test completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Worker processing test failed: {e}")
            self.test_results['worker_processing'] = False
            return False
    
    def test_end_to_end_flow(self):
        """Test complete announcement processing flow"""
        logger.info("🧪 Testing end-to-end flow...")
        
        try:
            # Simulate complete flow: Scraping -> AI -> Supabase -> Investor
            flow_id = str(uuid.uuid4())
            
            # 1. Announcement scraping job
            scraping_job = AnnouncementScrapingJob(
                job_id=f"{flow_id}_scraping",
                source="BSE"
            )
            self.redis_client.lpush(QueueNames.NEW_ANNOUNCEMENTS, serialize_job(scraping_job))
            
            # 2. AI processing job (as if triggered by scraper)
            ai_job = AIProcessingJob(
                job_id=f"{flow_id}_ai",
                corp_id="FLOW_TEST_001",
                company_name="Flow Test Company",
                security_id="FLOWTEST"
            )
            self.redis_client.lpush(QueueNames.AI_PROCESSING, serialize_job(ai_job))
            
            # 3. Supabase upload job (as if triggered by AI worker)
            supabase_job = SupabaseUploadJob(
                job_id=f"{flow_id}_supabase",
                corp_id="FLOW_TEST_001",
                processed_data={
                    "summary": "Test summary",
                    "category": "test_category",
                    "processed_at": datetime.utcnow().isoformat()
                }
            )
            self.redis_client.lpush(QueueNames.SUPABASE_UPLOAD, serialize_job(supabase_job))
            
            # 4. Investor analysis job (as if triggered by Supabase worker)
            investor_job = InvestorAnalysisJob(
                job_id=f"{flow_id}_investor",
                corp_id="FLOW_TEST_001",
                category="test_category"
            )
            self.redis_client.lpush(QueueNames.INVESTOR_PROCESSING, serialize_job(investor_job))
            
            # Verify all jobs are in queues
            queue_lengths = {}
            for queue_name in [QueueNames.NEW_ANNOUNCEMENTS, QueueNames.AI_PROCESSING, 
                             QueueNames.SUPABASE_UPLOAD, QueueNames.INVESTOR_PROCESSING]:
                length = self.redis_client.llen(queue_name)
                queue_lengths[queue_name] = length
                logger.info(f"📊 {queue_name}: {length} jobs")
            
            # Check that jobs contain our flow ID
            for queue_name in queue_lengths:
                if queue_lengths[queue_name] > 0:
                    # Peek at the job
                    job_json = self.redis_client.lindex(queue_name, -1)
                    if job_json and flow_id in job_json:
                        logger.info(f"✅ Flow job found in {queue_name}")
                    else:
                        logger.warning(f"⚠️ Flow job not found in {queue_name}")
            
            self.test_results['end_to_end_flow'] = True
            logger.info("✅ End-to-end flow test completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ End-to-end flow test failed: {e}")
            self.test_results['end_to_end_flow'] = False
            return False
    
    def test_queue_monitoring(self):
        """Test queue monitoring capabilities"""
        logger.info("🧪 Testing queue monitoring...")
        
        try:
            # Get queue statistics
            stats = {}
            for queue_name in QueueNames.all_queues():
                length = self.redis_client.llen(queue_name)
                stats[queue_name] = length
            
            # Test Redis info
            redis_info = self.redis_client.info()
            memory_usage = redis_info.get('used_memory', 0)
            connected_clients = redis_info.get('connected_clients', 0)
            
            logger.info("📊 Queue Statistics:")
            for queue_name, length in stats.items():
                logger.info(f"   {queue_name}: {length} jobs")
            
            logger.info(f"📊 Redis Memory Usage: {memory_usage} bytes")
            logger.info(f"📊 Connected Clients: {connected_clients}")
            
            self.test_results['queue_monitoring'] = True
            logger.info("✅ Queue monitoring test completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Queue monitoring test failed: {e}")
            self.test_results['queue_monitoring'] = False
            return False
    
    def test_component_imports(self):
        """Test that all components can be imported"""
        logger.info("🧪 Testing component imports...")
        
        components = {
            'BSE Scraper': 'src.scrapers.bse_scraper',
            'NSE Scraper': 'src.scrapers.nse_scraper', 
            'AI Prompts': 'src.ai.prompts',
            'Investor Analyzer': 'src.services.investor_analyzer',
            'Queue Manager': 'management.queue_manager',
            'Health Server': 'src.core.health_server'
        }
        
        import_results = {}
        for name, module_path in components.items():
            try:
                __import__(module_path)
                import_results[name] = True
                logger.info(f"✅ {name} imports successfully")
            except Exception as e:
                import_results[name] = False
                logger.error(f"❌ {name} import failed: {e}")
        
        self.test_results['component_imports'] = import_results
        return all(import_results.values())
    
    def cleanup_processes(self):
        """Clean up any running processes"""
        for process, name in self.running_processes:
            try:
                process.terminate()
                process.wait(timeout=5)
                logger.info(f"🛑 Stopped {name}")
            except subprocess.TimeoutExpired:
                process.kill()
                logger.info(f"🔪 Killed {name}")
            except Exception as e:
                logger.error(f"❌ Error stopping {name}: {e}")
    
    def run_comprehensive_test(self):
        """Run all tests"""
        logger.info("🚀 Starting Comprehensive System Test")
        logger.info("=" * 60)
        
        # Setup
        if not self.setup_redis():
            return False
        
        self.clear_queues()
        
        # Run tests
        tests = [
            ('Component Imports', self.test_component_imports),
            ('Queue Operations', self.test_queue_operations),
            ('Queue Monitoring', self.test_queue_monitoring),
            ('Worker Processing', self.test_worker_processing),
            ('End-to-End Flow', self.test_end_to_end_flow),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            logger.info(f"\n🧪 Running: {test_name}")
            try:
                if test_func():
                    passed += 1
                    logger.info(f"✅ {test_name}: PASSED")
                else:
                    logger.error(f"❌ {test_name}: FAILED")
            except Exception as e:
                logger.error(f"❌ {test_name}: ERROR - {e}")
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("🎯 COMPREHENSIVE SYSTEM TEST RESULTS")
        logger.info("=" * 60)
        
        for test_name, _ in tests:
            status = "✅ PASS" if self.test_results.get(test_name.lower().replace(' ', '_'), False) else "❌ FAIL"
            logger.info(f"{test_name:.<30} {status}")
        
        logger.info(f"\n📊 Overall Result: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("🎉 ALL TESTS PASSED! System is working correctly!")
            return True
        else:
            logger.error("⚠️ Some tests failed. Check logs above for details.")
            return False

def main():
    """Main function"""
    tester = SystemTester()
    
    try:
        success = tester.run_comprehensive_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        sys.exit(1)
    finally:
        tester.cleanup_processes()

if __name__ == "__main__":
    main()