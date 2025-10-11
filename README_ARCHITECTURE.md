# Backfin - Financial Announcement Processing System

## Architecture Overview

Backfin is a distributed system for processing BSE/NSE financial announcements using Redis queues and worker architecture.

## New Project Structure

```
backfin/
├── src/                          # Main application code
│   ├── core/                     # Core business logic
│   ├── queue/                    # Redis queue management  
│   ├── workers/                  # Worker implementations
│   ├── scrapers/                 # Web scraping logic
│   ├── ai/                       # AI processing (Gemini)
│   ├── database/                 # Database operations
│   ├── services/                 # Business services
│   └── utils/                    # Utility functions
│
├── workers/                      # Worker entry points
├── api/                          # REST API & monitoring
├── scripts/                      # Utility scripts
├── config/                       # Configuration files
└── deployment/                   # Docker & K8s configs
```

## Queue-Based Processing Flow

```
BSE Website → Scraper → Redis Queue → AI Workers → Supabase
                ↓
         NEW_ANNOUNCEMENTS → AI_PROCESSING → SUPABASE_UPLOAD
```

## Quick Start

### Local Development with Redis

1. **Start Redis and services:**
   ```bash
   docker-compose -f docker-compose.redis.yml up -d
   ```

2. **Run individual workers:**
   ```bash
   # AI Processing Worker
   python workers/start_ai_worker.py
   
   # Database Upload Worker  
   python workers/start_db_worker.py
   
   # Scraper (Producer)
   python workers/start_scraper_worker.py
   ```

3. **Monitor queues:**
   ```bash
   python management/queue_manager.py status
   ```

## Migration from Old Structure

### File Mappings

| Old File | New Location | Purpose |
|----------|--------------|---------|
| `new_scraper.py` | `src/scrapers/bse_scraper.py` | BSE scraping logic |
| `replay.py` | `workers/replay_processor.py` | Background processor |
| `prompt.py` | `src/ai/prompts.py` | AI prompts |
| `liveserver.py` | `api/app.py` | Web API server |
| `mailer.py` | `src/services/notification_service.py` | Notifications |

### Queue Names

- `NEW_ANNOUNCEMENTS`: Fresh announcements from scraper
- `AI_PROCESSING`: Announcements needing AI analysis  
- `SUPABASE_UPLOAD`: Processed data ready for database
- `INVESTOR_PROCESSING`: Investor analysis jobs
- `FAILED_JOBS`: Failed jobs for retry

## Development Workflow

### Adding New Features

1. **New Job Type**: Add to `src/queue/job_types.py`
2. **New Worker**: Create in `src/workers/` + entry point in `workers/`
3. **New Service**: Add to `src/services/`

### Testing

```bash
# Unit tests
python -m pytest tests/

# Integration tests
python -m pytest tests/integration/

# Test specific components
python scripts/test_components.py
```

### Monitoring

- **Queue Status**: `python management/queue_manager.py`
- **Worker Health**: `python management/worker_manager.py status`
- **Web Dashboard**: http://localhost:8080 (when running)

## Deployment

### AWS Infrastructure

See `deployment/` directory for:
- Terraform/CDK configurations
- Kubernetes manifests
- Auto-scaling policies

### Cost Control

- Set AWS budgets with alerts
- Use Spot instances for workers
- Monitor queue depths for auto-scaling

## Environment Variables

```bash
# Redis
REDIS_URL=redis://localhost:6379

# Supabase  
SUPABASE_URL2=your_supabase_url
SUPABASE_KEY2=your_supabase_key

# AI Processing
GEMINI_API_KEY=your_gemini_key

# Workers
WORKER_TYPE=ai_processor|database_uploader|scraper
```

## Scaling Strategy

- **Never scale**: Scraper (single instance only)
- **Scale horizontally**: AI workers, API instances
- **Scale based on queue depth**: Auto-scaling groups

## Support

For issues or questions, check:
1. Queue status: Are jobs stuck?
2. Worker logs: `logs/workers/`
3. Redis connection: Can workers connect?
4. AWS costs: Monitor spending alerts