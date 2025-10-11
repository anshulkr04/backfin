# Migration Guide: From Flat Structure to Redis Queue Architecture

## Overview

This branch (`markback`) implements the Redis Queue Architecture discussed earlier. It restructures the codebase for better scalability, maintainability, and production readiness.

## Key Changes

### 1. Directory Restructure ✅
- **All files moved** to logical directories with preserved git history
- **New structure** follows microservices patterns
- **Import paths** will need updates (see below)

### 2. Redis Queue System ✅  
- **Queue definitions** in `src/queue/`
- **Job types** with Pydantic validation
- **Worker framework** for distributed processing

### 3. Management Tools ✅
- **Queue monitoring**: `python management/queue_manager.py status`
- **Worker management**: `python management/worker_manager.py status`
- **Docker setup**: `docker-compose.redis.yml`

## Breaking Changes

### Import Path Updates Required

After merging this branch, you'll need to update imports in existing code:

```python
# OLD IMPORTS (will break)
from prompt import all_prompt
from invanl import uploadInvestor  
from mailer import send_email

# NEW IMPORTS (update to these)
from src.ai.prompts import all_prompt
from src.services.investor_analyzer import uploadInvestor
from src.services.notification_service import send_email
```

### File Location Changes

| Old Location | New Location |
|--------------|--------------|
| `new_scraper.py` | `src/scrapers/bse_scraper.py` |
| `replay.py` | `workers/replay_processor.py` |
| `prompt.py` | `src/ai/prompts.py` |
| `liveserver.py` | `api/app.py` |
| `mailer.py` | `src/services/notification_service.py` |
| `invanl.py` | `src/services/investor_analyzer.py` |

## Migration Steps

### 1. Test Current Functionality (Before Merge)
```bash
# Test your current setup works
python new_scraper.py  # Should work on main branch
python replay.py --date 2025-10-10  # Should work on main branch
```

### 2. Merge This Branch
```bash
git checkout main
git merge markback
```

### 3. Update Import Statements
Go through each file and update import statements as shown above.

### 4. Install New Dependencies
```bash
pip install redis psutil pydantic
```

### 5. Test Redis Setup (Optional)
```bash
# Start Redis locally
docker-compose -f docker-compose.redis.yml up -d redis

# Test queue manager
python management/queue_manager.py status
```

### 6. Update Your Scripts
Your current scripts will need import path updates:

**For bse_scraper.py:**
```python
# Update these imports at the top
from src.ai.prompts import all_prompt, category_prompt, headline_prompt
from src.services.investor_analyzer import uploadInvestor
```

**For replay_processor.py:**
```python
# Update these imports at the top  
from src.ai.prompts import all_prompt, category_prompt, headline_prompt
from src.services.investor_analyzer import uploadInvestor
```

## Testing Migration

### Quick Test
```bash
# After merging and updating imports
cd /path/to/backfin
python src/scrapers/bse_scraper.py  # Should work
python workers/replay_processor.py --date 2025-10-10  # Should work
```

### Full Redis Test
```bash
# Start Redis
docker-compose -f docker-compose.redis.yml up -d

# Start a worker
python workers/start_ai_worker.py

# Monitor queues
python management/queue_manager.py status
```

## Rollback Plan

If anything breaks:

```bash
# Quick rollback to old structure
git checkout main
git reset --hard HEAD~1  # Undo the merge

# Or create a hotfix branch
git checkout -b hotfix-imports-broken
# Fix imports there
```

## Benefits After Migration

1. **Scalable**: Can run multiple AI workers
2. **Reliable**: Jobs survive crashes with Redis persistence  
3. **Monitorable**: Clear visibility into processing pipeline
4. **Professional**: Industry-standard directory structure
5. **Docker Ready**: Full containerization support

## Support

- **Queue issues**: `python management/queue_manager.py status`
- **Worker issues**: `python management/worker_manager.py status`
- **Import errors**: Check the import mapping table above
- **Redis issues**: Ensure Redis is running (`docker-compose up redis`)

This is a significant architectural upgrade that sets up the foundation for production scaling!