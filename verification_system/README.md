# 📋 Production-Ready Verification System

A comprehensive, database-driven verification system for AI-processed announcements with real-time coordination, robust queue management, and zero data loss guarantee.

## 🏗️ Architecture Overview

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   Admin API         │    │   Queue Manager     │    │  Test Simulator     │
│   (REST + WebSocket)│    │   (Cleanup & Retry) │    │  (Dev Mode Only)    │
│   Port: 8002        │    │   Background Service│    │  Background Service │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
           │                           │                           │
           └─────────────┬─────────────┴─────────────┬─────────────┘
                        │                           │
                ┌─────────────────────┐    ┌─────────────────────┐
                │     Supabase        │    │      Redis          │
                │   (Primary Store)   │    │   (Coordination)    │
                │   Zero Data Loss    │    │   Real-time Sync    │
                └─────────────────────┘    └─────────────────────┘
```

## 🚀 Quick Start

```bash
# 1. Clone and setup
git clone [your-repo]
cd verification_system/

# 2. Run setup script
./setup.sh

# 3. Access the system
open http://localhost:8002
```

## 📦 Components

### 1. **Admin API Server** (`admin_api.py`)
- **REST API** for all verification operations
- **WebSocket** for real-time updates
- **JWT Authentication** with session management
- **Basic Web UI** for testing and administration

### 2. **Database Layer** (`core/database.py`)
- **Supabase integration** with full CRUD operations
- **Atomic task claiming** with `SKIP LOCKED`
- **Complete audit trail** in `admin_activity_log`
- **Edit tracking** in `verification_edits`

### 3. **Redis Coordination** (`core/redis_coordinator.py`)
- **Real-time presence** tracking for verifiers
- **Pub/Sub notifications** for task updates
- **Heartbeat management** with automatic cleanup
- **System-wide broadcasting**

### 4. **Queue Manager** (`core/queue_manager.py`)
- **Orphaned task recovery** when verifiers disconnect
- **Timeout handling** with automatic retry logic
- **Session cleanup** for expired admin sessions
- **Dead letter queue** for failed tasks

### 5. **Test Data Simulator** (`core/test_data_simulator.py`)
- **Development mode** simulation using `testdata.json`
- **Configurable timing** and batch processing
- **Production safety** with `PROD=false` requirement
- **Interactive CLI** for manual testing

### 6. **Authentication System** (`core/auth.py`)
- **Secure password hashing** with bcrypt
- **JWT session tokens** with expiration
- **Admin user management** with verification
- **Activity logging** for security

## 🔧 Configuration

### Environment Variables

```bash
# Production Mode
PROD=false                    # Set to true in production

# Database
SUPABASE_URL=your-url
SUPABASE_ANON_KEY=your-key

# Admin API
ADMIN_JWT_SECRET=your-secret  # MUST be 32+ characters in production
ADMIN_API_PORT=8002
ADMIN_SESSION_EXPIRE_HOURS=8

# Test Data (dev mode only)
TEST_DATA_INTERVAL=5          # Seconds between announcements
TEST_DATA_BATCH_SIZE=1        # Announcements per batch
TEST_DATA_START_DELAY=10      # Initial delay

# Queue Management
QUEUE_CLEANUP_INTERVAL=60     # Cleanup cycle interval
QUEUE_TASK_TIMEOUT=1800       # Task timeout (30 min)
QUEUE_SESSION_TIMEOUT=3600    # Session timeout (1 hour)
QUEUE_MAX_RETRIES=3          # Max retry attempts
```

## 🗄️ Database Schema

### Core Tables
- **`verification_tasks`** - Main task queue with status tracking
- **`verification_edits`** - Complete edit history
- **`admin_users`** - Admin user accounts
- **`admin_sessions`** - JWT session management
- **`admin_activity_log`** - Complete audit trail

### Task Status Flow
```
queued → in_progress → verified
   ↑         ↓
   └── (timeout/release)
```

## 🌐 API Endpoints

### Authentication
```bash
POST /auth/register    # Register new admin user
POST /auth/login       # Login and get JWT token
POST /auth/logout      # Logout current session
GET  /auth/me         # Get current user info
```

### Task Management
```bash
GET  /tasks           # List verification tasks
GET  /tasks/{id}      # Get specific task details
PUT  /tasks/{id}/claim    # Claim task for verification
PUT  /tasks/{id}/edit     # Edit announcement data
PUT  /tasks/{id}/verify   # Mark task as verified/rejected
PUT  /tasks/{id}/release  # Release task back to queue
```

### Monitoring
```bash
GET  /stats           # System statistics
GET  /                # Basic admin UI
```

### Development
```bash
POST /dev/create-sample-task    # Create single test task
POST /dev/create-sample-batch   # Create batch of test tasks
```

### WebSocket
```bash
WS   /ws?token=jwt    # Real-time updates
```

## 🔄 Workflow Examples

### 1. Admin User Registration & Login
```bash
# Register
curl -X POST http://localhost:8002/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"SecurePass123","name":"Admin User"}'

# Login
curl -X POST http://localhost:8002/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"SecurePass123"}'
```

### 2. Task Verification Process
```bash
# Get JWT token from login response
export TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."

# List available tasks
curl -H "Authorization: Bearer $TOKEN" http://localhost:8002/tasks

# Claim a task
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  http://localhost:8002/tasks/task-id/claim

# Edit announcement data
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"field_updates":{"headline":"Corrected headline"},"edit_reason":"Fixed typo"}' \
  http://localhost:8002/tasks/task-id/edit

# Verify task
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"verified":true,"notes":"Verified and edited"}' \
  http://localhost:8002/tasks/task-id/verify
```

### 3. WebSocket Real-time Updates
```javascript
const ws = new WebSocket(`ws://localhost:8002/ws?token=${jwt_token}`);

ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    console.log('Real-time update:', message);
};

// Send heartbeat
setInterval(() => {
    ws.send(JSON.stringify({type: 'heartbeat'}));
}, 30000);
```

## 🧪 Testing

### Development Mode
```bash
# Start with test data simulation
PROD=false ./setup.sh

# Create sample tasks
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8002/dev/create-sample-batch
```

### Interactive Simulator
```bash
# Run simulator in interactive mode
python core/test_data_simulator.py --interactive

# Commands available:
# start, stop, single, batch, stats, reset, quit
```

## 🐳 Docker Services

### Core Services (Always Running)
- **`verif-redis`** - Redis message broker
- **`verif-admin-api`** - Main API server
- **`verif-queue-manager`** - Background cleanup service

### Optional Services
- **`verif-simulator`** - Test data simulator (testing profile)
- **`verif-redis-ui`** - Redis management UI (debug profile)

### Service Management
```bash
# Start all services
docker-compose up -d

# Start with test simulator
docker-compose --profile testing up -d

# Start with Redis UI for debugging
docker-compose --profile debug up -d

# View logs
docker-compose logs -f admin-api
docker-compose logs -f queue-manager
docker-compose logs -f test-simulator

# Restart specific service
docker-compose restart admin-api

# Scale services
docker-compose up -d --scale queue-manager=2
```

## 📊 Monitoring

### System Statistics
```bash
# Get comprehensive stats
curl http://localhost:8002/stats | jq

# Key metrics:
# - tasks_queued, tasks_in_progress, tasks_verified
# - active_verifiers count
# - orphaned_tasks_cleaned
# - timeout_tasks_released
```

### Health Checks
```bash
# API health
curl -f http://localhost:8002/stats

# Redis connectivity
docker-compose exec redis redis-cli ping

# Database connectivity
curl -f http://localhost:8002/auth/me -H "Authorization: Bearer $TOKEN"
```

### Log Analysis
```bash
# System-wide logs
docker-compose logs --timestamps

# Filter by service
docker-compose logs admin-api | grep ERROR
docker-compose logs queue-manager | grep "Released"

# Real-time monitoring
docker-compose logs -f --tail=50
```

## 🔒 Security

### Production Checklist
- [ ] Change `ADMIN_JWT_SECRET` to 256-bit random string
- [ ] Set `PROD=true` to disable test simulator
- [ ] Configure proper CORS origins in FastAPI
- [ ] Use HTTPS with reverse proxy (nginx/traefik)
- [ ] Set up Supabase Row Level Security (RLS)
- [ ] Enable Redis authentication
- [ ] Configure firewall rules for ports
- [ ] Set up log rotation and monitoring

### Security Features
- **JWT tokens** with expiration and refresh
- **bcrypt password hashing** with salt
- **Session management** with timeout
- **Activity logging** for audit trail
- **Input validation** and sanitization
- **Rate limiting** protection
- **CORS protection** for web clients

## 🚨 Troubleshooting

### Common Issues

1. **Services won't start**
   ```bash
   docker-compose logs [service-name]
   docker-compose ps
   docker system df  # Check disk space
   ```

2. **Database connection errors**
   ```bash
   # Check Supabase credentials
   echo $SUPABASE_URL
   curl -I $SUPABASE_URL
   ```

3. **Redis connection errors**
   ```bash
   docker-compose exec redis redis-cli ping
   docker-compose logs redis
   ```

4. **Authentication failures**
   ```bash
   # Check JWT secret
   echo $ADMIN_JWT_SECRET
   # Verify token format
   python -c "import jwt; print(jwt.decode('$TOKEN', options={'verify_signature': False}))"
   ```

5. **Tasks not being processed**
   ```bash
   # Check queue manager
   docker-compose logs queue-manager
   # Check active verifiers
   curl http://localhost:8002/stats | jq .active_verifiers
   ```

### Recovery Procedures

1. **Reset all data**
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

2. **Clean orphaned tasks**
   ```bash
   # Restart queue manager
   docker-compose restart queue-manager
   ```

3. **Reset simulator**
   ```bash
   docker-compose restart test-simulator
   ```

## 🤝 Contributing

### Development Setup
```bash
# Local development
python -m venv venv
source venv/bin/activate
pip install -r requirements-admin.txt

# Run API locally
python admin_api.py

# Run tests
python -m pytest tests/
```

### Code Style
- **Black** for formatting
- **isort** for import sorting
- **mypy** for type checking
- **pytest** for testing

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues or questions:
1. Check the logs: `docker-compose logs [service]`
2. Verify configuration in `.env`
3. Review the troubleshooting section
4. Check system resource usage
5. Create an issue with logs and configuration

## 🗺️ Roadmap

- [ ] **Advanced UI** with React/Vue frontend
- [ ] **Bulk operations** for batch verification
- [ ] **Advanced filtering** and search
- [ ] **Metrics dashboard** with Grafana
- [ ] **Email notifications** for critical events
- [ ] **API rate limiting** with Redis
- [ ] **Multi-tenant support** with organization isolation
- [ ] **Machine learning** integration for auto-verification
- [ ] **Kubernetes deployment** manifests
- [ ] **CI/CD pipeline** with GitHub Actions