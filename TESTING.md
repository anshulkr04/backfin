# Testing Guide for Redis Queue Architecture

## Prerequisites & Setup

### 1. Install Dependencies
```bash
# Install new Redis dependencies
pip3 install redis psutil pydantic

# Or install all requirements
pip3 install -r requirements.txt
```

### 2. Install Redis (for full testing)
```bash
# macOS with Homebrew
brew install redis

# Start Redis server
redis-server

# Or use Docker
docker run -d -p 6379:6379 redis:alpine
```

## Testing Levels

### Level 1: Structure Test (No Redis Required)
```bash
# Test basic imports
python3 -c "
import sys
sys.path.append('.')
from src.queue.job_types import AIProcessingJob, QueueNames
from src.ai.prompts import all_prompt
print('✅ All modules import successfully')
"

# Test file movements
python3 -c "
from src.scrapers.bse_scraper import BseScraper
from src.services.investor_analyzer import uploadInvestor  
print('✅ Moved files import successfully')
"
```

### Level 2: Queue System Test (Redis Required)
```bash
# Start Redis first
redis-server &

# Test Redis connection
python3 -c "
from src.queue.redis_client import redis_client
redis_client.ping()
print('✅ Redis connection successful')
"

# Test queue operations
python3 management/queue_manager.py status
```

### Level 3: Worker Test (Full System)
```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start AI Worker
python3 workers/start_ai_worker.py

# Terminal 3: Monitor queues
python3 management/queue_manager.py status

# Terminal 4: Add test job (we'll create this script)
python3 scripts/test_queue_job.py
```

### Level 4: Integration Test
```bash
# Start full system with Docker
docker-compose -f docker-compose.redis.yml up -d

# Check all services
docker-compose -f docker-compose.redis.yml ps

# Monitor logs
docker-compose -f docker-compose.redis.yml logs -f
```

## Quick Test Scripts

### Test 1: Basic Structure Validation
Create and run: `scripts/test_structure.py`

### Test 2: Queue System Validation  
Create and run: `scripts/test_queue_system.py`

### Test 3: Worker System Validation
Create and run: `scripts/test_worker_system.py`

## Expected Results

### ✅ Success Indicators
- All imports work without errors
- Redis connects successfully
- Queues can be created and monitored
- Workers can process jobs
- Docker services start correctly

### ❌ Common Issues & Fixes
- **Import errors**: Run `pip3 install -r requirements.txt`
- **Redis connection failed**: Start Redis server
- **Module not found**: Check Python path and file locations
- **Docker issues**: Ensure Docker is running

## Performance Testing

### Load Test
```bash
# Add 100 test jobs
python3 scripts/load_test.py --jobs 100

# Monitor processing
watch -n 1 "python3 management/queue_manager.py status"
```

### Stress Test
```bash
# Start multiple workers
for i in {1..3}; do
    python3 workers/start_ai_worker.py &
done

# Add heavy load
python3 scripts/stress_test.py --jobs 1000
```

## Cleanup
```bash
# Stop all background processes
pkill -f "start_ai_worker"
pkill redis-server

# Or stop Docker
docker-compose -f docker-compose.redis.yml down
```