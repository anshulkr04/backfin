# Admin Verification System

A separate admin server for verifying AI-processed announcements from the main Flask backend.

## Architecture

```
Main Flask App (fin.anshulkr.com)
    ↓ (Redis Stream)
Admin Server (localhost:9000)
    ↓ (Database)
Verification Tasks
```

## Setup

### 1. Main Flask App Integration
The main Flask app now emits verification tasks to Redis Stream `admin:verification:stream` whenever a new announcement is processed.

### 2. Admin Server (Port 9000)
- **FastAPI** server with comprehensive admin functionality
- **Redis Streams** for task queue management
- **Supabase** for verification data storage
- **WebSocket** for real-time updates
- **JWT Authentication** for admin users

## Quick Start

### Start Admin Server
```bash
cd /Users/anshulkumar/backfin/admin_server
./start.sh
```

### Access Points
- **Dashboard**: http://localhost:9000/admin/dashboard
- **Registration**: http://localhost:9000/auth/register
- **Login**: http://localhost:9000/auth/login
- **API Docs**: http://localhost:9000/docs

## Workflow

1. **Announcement Created** → Main Flask app processes and emits to Redis
2. **Queue Processor** → Admin server picks up new tasks and creates verification records
3. **Admin Claims Task** → Admin user claims task from queue
4. **Admin Edits** → Make changes to announcement data
5. **Admin Verifies** → Approve/reject with notes
6. **Update Original** → Approved changes update the main database

## Key Features

### Authentication
- Register new admin users
- JWT-based session management
- Secure API endpoints

### Task Management
- Claim next available task
- Edit announcement fields
- Approve/reject with notes
- Release tasks back to queue
- Real-time task counts

### Admin Controls
- View all verification tasks
- Manual task reassignment
- User management
- System health monitoring
- Activity logging

### Real-time Updates
- WebSocket connections for live updates
- Task count notifications
- System broadcasts

## API Endpoints

### Authentication
- `POST /auth/register` - Register new admin
- `POST /auth/login` - Login
- `POST /auth/logout` - Logout

### Tasks
- `GET /tasks/next` - Claim next task
- `GET /tasks/my-current` - Get current task
- `PUT /tasks/{id}/field` - Edit task field
- `POST /tasks/{id}/verify` - Submit verification
- `POST /tasks/{id}/release` - Release task
- `GET /tasks/stats` - Get task statistics

### Admin
- `GET /admin/dashboard` - Admin dashboard HTML
- `GET /admin/stats` - Comprehensive statistics
- `GET /admin/tasks` - All verification tasks
- `GET /admin/users` - All admin users
- `GET /admin/activity` - Activity log
- `POST /admin/broadcast` - Broadcast message

## Database Schema

### verification_tasks
- Task details and current data
- Edit history tracking
- Assignment and status management

### admin_users
- Admin user accounts
- Authentication data

### admin_sessions
- JWT session management
- Session activity tracking

### admin_activity_log
- Comprehensive audit trail
- User action logging

## Configuration

### Environment Variables
```bash
REDIS_URL=redis://localhost:6379
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
JWT_SECRET_KEY=your_jwt_secret
ADMIN_SERVER_PORT=9000
```

### Redis Streams
- **Main Stream**: `admin:verification:stream`
- **Consumer Group**: `admin:verification:workers`
- **Consumer Pattern**: `user:{user_id}:session:{session_id}`

## Deployment

### Development
```bash
# Start admin server
cd admin_server
./start.sh

# Access dashboard
open http://localhost:9000/admin/dashboard
```

### Production
```bash
# Use gunicorn or similar
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:9000
```

## Integration with Main App

The main Flask app automatically sends tasks to the admin queue:

```python
# In main Flask app - announcement processing
if redis_client:
    admin_task = {
        "announcement": json.dumps(new_announcement),
        "original_data": json.dumps(data),
        "ai_summary": ai_summary
    }
    redis_client.xadd("admin:verification:stream", admin_task)
```

## Security

- JWT authentication for all admin endpoints
- Session-based user management
- Activity logging for audit trails
- CORS configuration for web dashboard
- Environment-based secrets

## Monitoring

- Real-time task statistics
- Redis stream monitoring
- Database connection health
- WebSocket connection counts
- Background service status

## Troubleshooting

### Common Issues

1. **Redis Connection**: Ensure Redis is running on localhost:6379
2. **Database**: Verify Supabase credentials in .env
3. **Port Conflicts**: Admin server uses port 9000
4. **WebSocket**: Check CORS settings for dashboard

### Logs
- Admin server logs to console
- Background services log task processing
- Activity log in database for audit trail

## Next Steps

1. **Deploy Admin Server** - Set up on separate subdomain/port
2. **Database Schema** - Run SQL migration for verification tables
3. **User Registration** - Create initial admin accounts
4. **Integration Testing** - Verify end-to-end workflow
5. **Production Config** - Environment-specific settings