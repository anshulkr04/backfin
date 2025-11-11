# Production-Safe Verification System Deployment Guide

## Overview

This verification system runs parallel to your existing announcement pipeline without any modifications to the core system. It provides a secure, scalable way to verify AI-processed announcements before they go live.

## Architecture

```
📡 Existing Pipeline               🔍 Verification Pipeline
                                  
Announcements → WebSocket Server  ┌─→ Announcement Tap
      ↓                          │         ↓
   AI Queue                      │   Verification Backlog
      ↓                          │         ↓
   Supabase                      │     Dispatcher
                                 │         ↓
                                 │   Round-Robin Assignment
                                 │         ↓
                                 └─→ Verifier UI ←→ Human Verifiers
```

## Components

1. **Announcement Tap** - Mirrors announcements to verification backlog
2. **Presence Gateway** - WebSocket server for verifier connections
3. **Dispatcher** - Round-robin task assignment with visibility timeout
4. **Verifier UI** - Web interface for human verification
5. **Redis** - Message broker and state management

## Quick Start

```bash
# 1. Set up the system
cd verification_system/
./setup.sh

# 2. Access the verifier UI
open http://localhost:8080

# 3. Monitor with Redis UI (optional)
docker-compose --profile debug up -d
open http://localhost:8081
```

## Configuration

### Environment Variables

Edit `.env` file for production settings:

```env
# Redis Configuration
REDIS_URL=redis://your-redis-host:6379

# JWT Secret (MUST change in production!)
JWT_SECRET=your-super-secret-jwt-key-256-bits-minimum

# Feature Flags
VERIFICATION_ENABLED=true

# Announcement Tap
LISTEN_CHANNELS=announcements,nse_announcements  # Channels to mirror
BACKLOG_STREAM=verif:backlog                      # Target stream
STATS_INTERVAL=60                                 # Statistics interval

# Presence Gateway
GATEWAY_PORT=8001                # WebSocket port
HEARTBEAT_INTERVAL=30            # Heartbeat frequency (seconds)
PRESENCE_TIMEOUT=60              # Verifier timeout (seconds)

# Dispatcher
DISPATCH_BATCH_SIZE=10           # Tasks per dispatch cycle
DISPATCH_INTERVAL=2              # Dispatch frequency (seconds)
VISIBILITY_TIMEOUT=120           # Task visibility timeout (seconds)
TIMEOUT_CHECK_INTERVAL=30        # Timeout check frequency (seconds)
MAX_RETRIES=3                    # Max retry attempts

# Logging
LOG_LEVEL=INFO                   # DEBUG, INFO, WARNING, ERROR
```

## Production Deployment

### 1. Security Considerations

```bash
# Generate secure JWT secret
openssl rand -base64 32

# Use secure Redis configuration
# - Enable authentication
# - Use TLS/SSL
# - Restrict network access
```

### 2. Scaling

```yaml
# Scale services based on load
services:
  dispatcher:
    deploy:
      replicas: 2  # Multiple dispatchers for high availability
  
  presence-gateway:
    deploy:
      replicas: 3  # Scale based on concurrent verifiers
    ports:
      - "8001-8003:8001"  # Load balance across ports
```

### 3. Monitoring

```yaml
# Add monitoring services
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

## Integration with Existing System

### 1. Enable Mirroring

Add Redis pub/sub to your existing WebSocket announcement handler:

```python
# In your existing announcement handler
async def handle_announcement(data):
    # Existing logic...
    await process_with_ai(data)
    await save_to_supabase(data)
    
    # NEW: Mirror to verification system
    if verification_enabled:
        redis_client.publish('announcements', json.dumps(data))
```

### 2. JWT Token Generation

Create tokens for verifiers in your admin system:

```python
import jwt
from datetime import datetime, timedelta

def create_verifier_token(verifier_id, permissions=None):
    payload = {
        'sub': verifier_id,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=8),
        'permissions': permissions or ['verify']
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')
```

### 3. Feature Flag Control

```python
# Environment or database setting
VERIFICATION_ENABLED = os.getenv('VERIFICATION_ENABLED', 'false').lower() == 'true'

# Gradual rollout by percentage
VERIFICATION_PERCENTAGE = int(os.getenv('VERIFICATION_PERCENTAGE', '0'))

def should_verify_announcement(ann_id):
    if not VERIFICATION_ENABLED:
        return False
    
    # Hash-based consistent sampling
    return hash(ann_id) % 100 < VERIFICATION_PERCENTAGE
```

## Redis Data Model

### Keys Used

```
# Presence Management
verifiers:active              # Set of active verifier IDs
verifier:<id>:presence        # Individual presence with TTL

# Task Queues
verif:backlog                 # Stream of announcements to verify
verif:assign:<verifier_id>    # Per-verifier assignment streams
verif:pending:<verifier_id>   # Sorted set of pending tasks

# Round-Robin State
verif:last_index             # Last used verifier index

# Operational
verif:inflight:<ann_id>      # Inflight task locks
verif:retries:<ann_id>       # Retry counters
verif:deadletter             # Failed tasks
verif:rebalance              # Rebalance trigger channel
```

### Message Formats

```json
// Announcement in backlog
{
  "id": "ann_123",
  "payload": "{\"title\":\"...\",\"content\":\"...\"}",
  "ts": "2024-01-15T10:30:00Z",
  "source": "nse_scraper"
}

// Task assignment
{
  "id": "ann_123",
  "payload": "{...}",
  "assigned_at": "2024-01-15T10:30:05Z",
  "source_stream_id": "1642248605000-0"
}

// WebSocket message
{
  "type": "task_assignment",
  "data": {
    "id": "ann_123",
    "payload": "{...}",
    "assigned_at": "2024-01-15T10:30:05Z"
  }
}
```

## Troubleshooting

### Common Issues

1. **Services won't start**
   ```bash
   # Check Docker logs
   docker-compose logs [service-name]
   
   # Verify Redis connectivity
   docker-compose exec redis redis-cli ping
   ```

2. **WebSocket connection fails**
   ```bash
   # Check gateway logs
   docker-compose logs verif-gateway
   
   # Verify JWT token format
   # Should be: eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
   ```

3. **Tasks not being dispatched**
   ```bash
   # Check dispatcher logs
   docker-compose logs verif-dispatcher
   
   # Verify active verifiers
   docker-compose exec redis redis-cli SMEMBERS verifiers:active
   
   # Check backlog
   docker-compose exec redis redis-cli XLEN verif:backlog
   ```

4. **High memory usage**
   ```bash
   # Monitor Redis memory
   docker-compose exec redis redis-cli info memory
   
   # Set stream maxlen
   docker-compose exec redis redis-cli XTRIM verif:backlog MAXLEN ~ 1000
   ```

### Health Checks

```bash
# Service health
curl http://localhost:8080/  # UI should load
curl http://localhost:8081/  # Redis UI (if enabled)

# WebSocket connection
wscat -c ws://localhost:8001?token=YOUR_JWT_TOKEN

# Redis connectivity
docker-compose exec redis redis-cli ping
```

### Monitoring Queries

```bash
# Active verifiers
redis-cli SMEMBERS verifiers:active

# Backlog size
redis-cli XLEN verif:backlog

# Pending tasks per verifier
for id in $(redis-cli SMEMBERS verifiers:active); do
  echo "$id: $(redis-cli ZCARD verif:pending:$id)"
done

# Dead letter count
redis-cli XLEN verif:deadletter
```

## Maintenance

### Regular Tasks

```bash
# 1. Clean old streams (weekly)
./cleanup.sh

# 2. Monitor performance
docker-compose exec redis redis-cli info stats

# 3. Backup Redis data
docker-compose exec redis redis-cli BGSAVE
```

### Updates

```bash
# 1. Pull latest changes
git pull origin main

# 2. Rebuild services
docker-compose build

# 3. Rolling restart
docker-compose up -d --no-deps --force-recreate [service]
```

## Support

For issues or questions:

1. Check logs: `docker-compose logs [service]`
2. Verify configuration in `.env`
3. Test components individually
4. Review Redis key patterns
5. Monitor resource usage

The system is designed to be resilient and self-healing. Most issues resolve automatically through retries and rebalancing.