#!/usr/bin/env python3
"""
Test data simulation system for development
Feeds testdata.json announcements into verification queue
"""

import os
import asyncio
import json
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import uuid

from core.database import DatabaseManager
from core.redis_coordinator import RedisCoordinator

logger = logging.getLogger(__name__)

class TestDataSimulator:
    def __init__(self):
        self.db = DatabaseManager()
        self.redis = RedisCoordinator()
        
        # Configuration
        self.prod_mode = os.getenv('PROD', 'false').lower() == 'true'
        self.test_data_file = Path(__file__).parent / 'testdata.json'
        self.interval = int(os.getenv('TEST_DATA_INTERVAL', '5'))  # seconds between announcements
        self.batch_size = int(os.getenv('TEST_DATA_BATCH_SIZE', '1'))  # announcements per batch
        self.start_delay = int(os.getenv('TEST_DATA_START_DELAY', '10'))  # initial delay
        
        # State
        self.running = False
        self.test_data = []
        self.current_index = 0
        self.stats = {
            'total_loaded': 0,
            'total_processed': 0,
            'total_created': 0,
            'errors': 0,
            'started_at': None
        }

    async def initialize(self):
        """Initialize database and Redis connections"""
        logger.info("🚀 Initializing Test Data Simulator")
        
        # Check production mode
        if self.prod_mode:
            logger.info("🏭 Production mode detected, simulator disabled")
            return False
        
        # Connect to database
        if not await self.db.connect():
            logger.error("❌ Failed to connect to database")
            return False
        
        # Connect to Redis
        if not await self.redis.connect():
            logger.error("❌ Failed to connect to Redis")
            return False
        
        # Load test data
        if not await self.load_test_data():
            logger.error("❌ Failed to load test data")
            return False
        
        logger.info("✅ Test Data Simulator initialized successfully")
        return True

    async def load_test_data(self):
        """Load test data from JSON file"""
        try:
            if not self.test_data_file.exists():
                logger.error(f"❌ Test data file not found: {self.test_data_file}")
                return False
            
            with open(self.test_data_file, 'r', encoding='utf-8') as f:
                self.test_data = json.load(f)
            
            self.stats['total_loaded'] = len(self.test_data)
            logger.info(f"✅ Loaded {len(self.test_data)} test announcements from {self.test_data_file}")
            
            # Log sample data structure
            if self.test_data:
                sample = self.test_data[0]
                logger.info(f"📄 Sample announcement fields: {list(sample.keys())}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error loading test data: {e}")
            return False

    async def create_verification_task_from_announcement(self, announcement: Dict[str, Any]) -> Optional[str]:
        """Create a verification task from announcement data"""
        try:
            # Extract announcement ID (use corp_id as announcement_id)
            announcement_id = announcement.get('corp_id')
            if not announcement_id:
                logger.warning("⚠️ Announcement missing corp_id, generating UUID")
                announcement_id = str(uuid.uuid4())
            
            # Prepare announcement data for verification
            original_data = {
                'corp_id': announcement_id,
                'securityid': announcement.get('securityid'),
                'summary': announcement.get('summary'),
                'fileurl': announcement.get('fileurl'),
                'date': announcement.get('date'),
                'ai_summary': announcement.get('ai_summary'),
                'category': announcement.get('category'),
                'isin': announcement.get('isin'),
                'companyname': announcement.get('companyname'),
                'symbol': announcement.get('symbol'),
                'headline': announcement.get('headline'),
                'sentiment': announcement.get('sentiment'),
                'company_id': announcement.get('company_id'),
                'index_date': announcement.get('index_date'),
                # Metadata
                'simulated': True,
                'simulated_at': datetime.utcnow().isoformat(),
                'source': 'test_data_simulator'
            }
            
            # Create verification task
            task = await self.db.create_verification_task(
                announcement_id=announcement_id,
                original_data=original_data
            )
            
            # Notify via Redis
            task_data = {
                'id': task.id,
                'announcement_id': task.announcement_id,
                'company': original_data.get('companyname', 'Unknown'),
                'category': original_data.get('category', 'Unknown'),
                'created_at': task.created_at.isoformat()
            }
            
            await self.redis.notify_new_task(task_data)
            
            logger.info(f"✅ Created verification task {task.id} for announcement {announcement_id}")
            self.stats['total_created'] += 1
            
            return task.id
            
        except Exception as e:
            logger.error(f"❌ Error creating verification task: {e}")
            self.stats['errors'] += 1
            return None

    async def process_batch(self) -> int:
        """Process a batch of announcements"""
        if self.current_index >= len(self.test_data):
            logger.info("📝 All test data processed, restarting from beginning")
            self.current_index = 0
        
        batch_end = min(self.current_index + self.batch_size, len(self.test_data))
        batch = self.test_data[self.current_index:batch_end]
        
        tasks_created = 0
        
        for announcement in batch:
            task_id = await self.create_verification_task_from_announcement(announcement)
            if task_id:
                tasks_created += 1
            
            self.stats['total_processed'] += 1
        
        self.current_index = batch_end
        
        logger.info(f"📦 Processed batch of {len(batch)} announcements, created {tasks_created} tasks")
        return tasks_created

    async def run(self):
        """Main simulation loop"""
        if self.prod_mode:
            logger.info("🏭 Production mode - simulation skipped")
            return
        
        if not self.test_data:
            logger.error("❌ No test data available")
            return
        
        self.running = True
        self.stats['started_at'] = datetime.utcnow().isoformat()
        
        logger.info(f"⏰ Starting simulation in {self.start_delay} seconds...")
        logger.info(f"⚙️ Configuration:")
        logger.info(f"   Interval: {self.interval}s")
        logger.info(f"   Batch size: {self.batch_size}")
        logger.info(f"   Total announcements: {len(self.test_data)}")
        
        # Initial delay
        await asyncio.sleep(self.start_delay)
        
        try:
            while self.running:
                start_time = datetime.utcnow()
                
                # Process batch
                tasks_created = await self.process_batch()
                
                # Update stats
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                
                # Log progress periodically
                if self.stats['total_processed'] % 10 == 0:
                    logger.info(f"📊 Progress: {self.stats['total_processed']}/{len(self.test_data)} "
                              f"({self.stats['total_processed']/len(self.test_data)*100:.1f}%)")
                
                # Update Redis stats
                await self.redis.update_stats({
                    'simulator_running': 'true',
                    'simulator_processed': str(self.stats['total_processed']),
                    'simulator_created': str(self.stats['total_created']),
                    'simulator_errors': str(self.stats['errors']),
                    'simulator_current_index': str(self.current_index),
                    'simulator_processing_time': f"{processing_time:.2f}s"
                })
                
                # Wait for next batch
                await asyncio.sleep(self.interval)
                
        except asyncio.CancelledError:
            logger.info("🛑 Simulation cancelled")
        except Exception as e:
            logger.error(f"❌ Error in simulation loop: {e}")
        finally:
            self.running = False
            await self.cleanup()

    async def cleanup(self):
        """Cleanup resources"""
        logger.info("🧹 Cleaning up simulator...")
        
        # Update final stats
        await self.redis.update_stats({
            'simulator_running': 'false',
            'simulator_stopped_at': datetime.utcnow().isoformat()
        })
        
        # Close connections
        await self.redis.disconnect()
        await self.db.close()
        
        # Log final stats
        logger.info("📊 Final simulation statistics:")
        logger.info(f"   Total processed: {self.stats['total_processed']}")
        logger.info(f"   Tasks created: {self.stats['total_created']}")
        logger.info(f"   Errors: {self.stats['errors']}")
        
        if self.stats['started_at']:
            duration = datetime.utcnow() - datetime.fromisoformat(self.stats['started_at'])
            logger.info(f"   Runtime: {duration}")

    def stop(self):
        """Stop the simulation"""
        logger.info("🛑 Stopping simulation...")
        self.running = False

    async def get_stats(self) -> Dict[str, Any]:
        """Get current simulation statistics"""
        return {
            **self.stats,
            'current_index': self.current_index,
            'remaining': len(self.test_data) - self.current_index if self.test_data else 0,
            'progress_percent': round((self.current_index / len(self.test_data)) * 100, 1) if self.test_data else 0,
            'running': self.running
        }

    # ============================================================================
    # Development Utilities
    # ============================================================================
    
    async def create_single_announcement(self, index: int = 0) -> Optional[str]:
        """Create a single announcement for testing"""
        if index >= len(self.test_data):
            logger.error(f"❌ Index {index} out of range (max: {len(self.test_data) - 1})")
            return None
        
        announcement = self.test_data[index]
        return await self.create_verification_task_from_announcement(announcement)

    async def create_sample_batch(self, count: int = 5) -> List[str]:
        """Create a sample batch of announcements"""
        task_ids = []
        
        for i in range(min(count, len(self.test_data))):
            task_id = await self.create_verification_task_from_announcement(self.test_data[i])
            if task_id:
                task_ids.append(task_id)
        
        logger.info(f"✅ Created sample batch of {len(task_ids)} tasks")
        return task_ids

    async def reset_simulation(self):
        """Reset simulation state"""
        self.current_index = 0
        self.stats = {
            'total_loaded': len(self.test_data),
            'total_processed': 0,
            'total_created': 0,
            'errors': 0,
            'started_at': None
        }
        logger.info("🔄 Simulation state reset")

class SimulatorCLI:
    """Command-line interface for the simulator"""
    
    def __init__(self):
        self.simulator = TestDataSimulator()
        
    async def run_interactive(self):
        """Run interactive CLI"""
        if not await self.simulator.initialize():
            return
        
        print("\n🎛️ Test Data Simulator CLI")
        print("Commands:")
        print("  start     - Start continuous simulation")
        print("  stop      - Stop simulation") 
        print("  single    - Create single announcement")
        print("  batch     - Create sample batch (5 items)")
        print("  stats     - Show statistics")
        print("  reset     - Reset simulation state")
        print("  quit      - Exit")
        
        while True:
            try:
                cmd = input("\nsim> ").strip().lower()
                
                if cmd == 'start':
                    print("🚀 Starting simulation...")
                    asyncio.create_task(self.simulator.run())
                
                elif cmd == 'stop':
                    self.simulator.stop()
                    print("🛑 Stopping simulation...")
                
                elif cmd == 'single':
                    task_id = await self.simulator.create_single_announcement()
                    print(f"✅ Created task: {task_id}")
                
                elif cmd == 'batch':
                    task_ids = await self.simulator.create_sample_batch()
                    print(f"✅ Created batch of {len(task_ids)} tasks")
                
                elif cmd == 'stats':
                    stats = await self.simulator.get_stats()
                    print("📊 Statistics:")
                    for key, value in stats.items():
                        print(f"   {key}: {value}")
                
                elif cmd == 'reset':
                    await self.simulator.reset_simulation()
                    print("🔄 Simulation reset")
                
                elif cmd in ('quit', 'exit', 'q'):
                    break
                
                else:
                    print("❓ Unknown command")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        await self.simulator.cleanup()

async def main():
    """Main entry point"""
    simulator = TestDataSimulator()
    
    # Signal handlers
    def signal_handler(signum, frame):
        logger.info(f"📨 Received signal {signum}")
        simulator.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize and run
    if await simulator.initialize():
        await simulator.run()
    else:
        logger.error("❌ Failed to initialize simulator")
        sys.exit(1)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Check for interactive mode
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        asyncio.run(SimulatorCLI().run_interactive())
    else:
        asyncio.run(main())