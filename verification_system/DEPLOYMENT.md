# Deployment Guide

## Quick Deployment Steps

### 1. Prerequisites
- Docker and Docker Compose installed
- Supabase account with project created
- Google Gemini API key

### 2. Setup Environment

```bash
# Clone repository
git clone <repository-url>
cd backfin

# Edit the main .env file (not verification_system/.env)
nano .env
```

### 3. Configure Main .env File

The verification system uses the main `.env` file in the `backfin` directory. Add the following values:

```env
# Supabase Configuration for Verification System
# (from https://app.supabase.com/project/_/settings/api)
SUPABASE_URL2=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# JWT Secret (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET_KEY=your_generated_secret_key

# Gemini API (from https://makersuite.google.com/app/apikey)
GEMINI_API_KEY=your_gemini_api_key

# Optional: Prompt for AI content generation
PROMPT=your_custom_prompt_here
```

**Important:** The verification system uses `SUPABASE_URL2` (not `SUPABASE_URL`) to avoid conflicts with other services in the main application.

### 4. Database Setup

Run the following SQL in your Supabase SQL Editor:

```sql
-- Create admin_users table
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create admin_sessions table
CREATE TABLE IF NOT EXISTS admin_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES admin_users(id) ON DELETE CASCADE,
    session_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add verification columns to corporatefilings if not exists
ALTER TABLE corporatefilings 
ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS verified_by UUID REFERENCES admin_users(id);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_admin_sessions_user_id ON admin_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_token ON admin_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_corporatefilings_verified ON corporatefilings(verified);
CREATE INDEX IF NOT EXISTS idx_corporatefilings_timestamp ON corporatefilings(timestamp DESC);
```

### 5. Deploy with Docker Compose

```bash
# Build and start the service
docker-compose up -d

# Check logs
docker-compose logs -f verification-api

# Verify health
curl http://localhost:5002/health
```

Expected output:
```json
{
  "status": "healthy",
  "app": "Backfin Verification System",
  "version": "1.0.0",
  "mode": "production"
}
```

### 6. Create First Admin User

```bash
# Register admin user
curl -X POST http://localhost:5002/api/admin/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@yourcompany.com",
    "password": "YourSecurePassword123!",
    "name": "Admin User"
  }'
```

### 7. Test the API

```bash
# Login to get token
TOKEN=$(curl -X POST http://localhost:5002/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@yourcompany.com",
    "password": "YourSecurePassword123!"
  }' | jq -r '.access_token')

# Test get announcements
curl -X GET "http://localhost:5002/api/admin/announcements?limit=5" \
  -H "Authorization: Bearer $TOKEN"

# Test AI content generation
curl -X POST http://localhost:5002/api/admin/generate-content \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fileurl": "https://www.bseindia.com/xml-data/corpfiling/AttachLive/example.pdf",
    "model": "gemini-2.5-flash-lite"
  }'
```

## Production Considerations

### 1. Security
- [ ] Change default JWT_SECRET_KEY to a strong random value
- [ ] Use environment-specific CORS origins (not *)
- [ ] Enable HTTPS with reverse proxy (nginx/traefik)
- [ ] Implement rate limiting
- [ ] Regular security audits

### 2. Monitoring
```bash
# View logs in real-time
docker-compose logs -f verification-api

# Check container stats
docker stats backfin-verification-api

# Access interactive docs
open http://localhost:5002/docs
```

### 3. Backup
- Regular database backups via Supabase
- Export environment variables securely
- Version control configuration files (except .env)

### 4. Scaling
- Use Docker Swarm or Kubernetes for multi-instance deployment
- Configure load balancer for multiple API instances
- Consider Redis for session management at scale
- Monitor Gemini API quota and costs

### 5. Updates
```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Check health after update
curl http://localhost:5002/health
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs verification-api

# Common issues:
# - Missing environment variables in .env
# - Invalid Supabase credentials
# - Port 5002 already in use
```

### Database connection errors
```bash
# Verify Supabase credentials
# Check if service role key has proper permissions
# Ensure Supabase project is active
```

### AI generation fails
```bash
# Verify GEMINI_API_KEY is set correctly
# Check API quota on Google AI Studio
# Test with smaller/different PDF files
# Check logs for specific error messages
```

### Health check fails
```bash
# Check if port is accessible
curl http://localhost:5002/health

# Restart container
docker-compose restart verification-api

# Check container health status
docker ps
```

## Maintenance

### View Logs
```bash
docker-compose logs -f verification-api
```

### Restart Service
```bash
docker-compose restart verification-api
```

### Stop Service
```bash
docker-compose down
```

### Update Dependencies
```bash
# Edit requirements.txt
nano requirements.txt

# Rebuild
docker-compose up -d --build
```

## Support

For issues and questions:
- Check logs: `docker-compose logs verification-api`
- Review API docs: `http://localhost:5002/docs`
- Create GitHub issue with logs and error details

---

**Deployment completed! 🚀**

Access the API at: `http://localhost:5002`
Interactive docs at: `http://localhost:5002/docs`
