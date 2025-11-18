# Backfin Verification System API

A FastAPI-based verification and AI content generation system for corporate filings with Supabase PostgreSQL and Google Gemini AI integration.

## 🚀 Quick Start

### Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd backfin/verification_system

# Configure environment variables
cp .env.example .env
# Edit .env with your credentials

# Start the service
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop the service
docker-compose down
```

The API will be available at `http://localhost:5002`

### Manual Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure .env file with your credentials
# Run the application
python app.py
```

## 🏗️ Architecture

- **Framework**: FastAPI (Python async web framework)
- **Database**: Supabase PostgreSQL
- **Authentication**: JWT tokens with bcrypt hashing
- **AI Integration**: Google Gemini 2.5 (flash-lite & flash-pro)
- **PDF Processing**: PyPDF2 for page extraction

## 🔑 Environment Variables

This service uses the main `.env` file located in the parent directory (`/Users/anshulkumar/backfin/.env`).

Add the following variables to your main `.env` file:

```env
# Supabase Configuration for Verification System
SUPABASE_URL2=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# JWT Secret for Verification System
JWT_SECRET_KEY=your_jwt_secret_key_min_32_chars

# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key

# Optional: Server Configuration
# HOST=0.0.0.0
# PORT=5002
# DEBUG=false
# PROD=true
```

**Note:** The verification system uses `SUPABASE_URL2` and `SUPABASE_SERVICE_ROLE_KEY` from the main `.env` file to avoid duplication with other services.

## 📚 API Documentation

### Base URL
```
http://localhost:5002/api/admin
```

All endpoints except registration and login require authentication via Bearer token.

---

## 🔐 Authentication

### 1. Register New Admin User

**Endpoint:** `POST /api/admin/auth/register`

**Request Body:**
```json
{
  "email": "admin@example.com",
  "password": "SecurePassword123!",
  "name": "John Doe"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid-here",
    "email": "admin@example.com",
    "name": "John Doe"
  }
}
```

### 2. Login

**Endpoint:** `POST /api/admin/auth/login`

**Request Body:**
```json
{
  "email": "admin@example.com",
  "password": "SecurePassword123!"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid-here",
    "email": "admin@example.com",
    "name": "John Doe"
  }
}
```

### 3. Logout

**Endpoint:** `POST /api/admin/auth/logout`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "message": "Logged out successfully"
}
```

### 4. Get Current User

**Endpoint:** `GET /api/admin/auth/me`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "id": "uuid-here",
  "email": "admin@example.com",
  "name": "John Doe",
  "created_at": "2025-11-18T10:30:00"
}
```

---

## 📝 Announcement Management

### 5. Get Announcements

**Endpoint:** `GET /api/admin/announcements`

**Query Parameters:**
- `verified` (boolean): Filter by verification status (default: false)
- `limit` (integer): Number of results (default: 50)
- `offset` (integer): Pagination offset (default: 0)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Example Request:**
```
GET /api/admin/announcements?verified=false&limit=10&offset=0
```

**Response (200):**
```json
{
  "announcements": [
    {
      "corp_id": "550e8400-e29b-41d4-a716-446655440000",
      "announcement": "Board Meeting",
      "description": "Meeting scheduled for Q3 results",
      "summary": "Original summary text",
      "headline": "Company Board Meeting Announcement",
      "category": "Board Meetings",
      "ai_summary": "AI generated summary",
      "sentiment": "Neutral",
      "fileurl": "https://example.com/file.pdf",
      "verified": false,
      "timestamp": "2025-11-18T10:00:00"
    }
  ],
  "count": 10,
  "offset": 0,
  "limit": 10
}
```

### 6. Get Single Announcement

**Endpoint:** `GET /api/admin/announcements/{corp_id}`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "corp_id": "550e8400-e29b-41d4-a716-446655440000",
  "announcement": "Board Meeting",
  "description": "Meeting details",
  "summary": "Summary text",
  "headline": "Meeting Headline",
  "category": "Board Meetings",
  "ai_summary": "AI summary",
  "sentiment": "Neutral",
  "companyname": "Example Corp Ltd",
  "symbol": "EXAMPLE",
  "fileurl": "https://example.com/file.pdf",
  "verified": false,
  "verified_at": null,
  "verified_by": null,
  "timestamp": "2025-11-18T10:00:00"
}
```

### 7. Update Announcement

**Endpoint:** `PATCH /api/admin/announcements/{corp_id}`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body (all fields optional):**
```json
{
  "announcement": "Updated announcement text",
  "description": "Updated description",
  "summary": "Updated summary",
  "headline": "Updated headline",
  "category": "Financial Results",
  "ai_summary": "Updated AI summary",
  "sentiment": "Positive",
  "companyname": "Updated Company Name",
  "symbol": "SYMBOL"
}
```

**Response (200):**
```json
{
  "success": true,
  "corp_id": "550e8400-e29b-41d4-a716-446655440000",
  "updated": {
    "corp_id": "550e8400-e29b-41d4-a716-446655440000",
    "headline": "Updated headline",
    "category": "Financial Results",
    "ai_summary": "Updated AI summary",
    "sentiment": "Positive"
  }
}
```

### 8. Verify Announcement

**Endpoint:** `POST /api/admin/announcements/{corp_id}/verify`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body (optional):**
```json
{
  "notes": "Verified after review"
}
```

**Response (200):**
```json
{
  "success": true,
  "corp_id": "550e8400-e29b-41d4-a716-446655440000",
  "verified_at": "2025-11-18T14:30:00",
  "verified_by": "uuid-of-verifier",
  "message": "Announcement verified successfully"
}
```

### 9. Unverify Announcement

**Endpoint:** `POST /api/admin/announcements/{corp_id}/unverify`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "success": true,
  "corp_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Verification removed successfully"
}
```

---

## 🤖 AI Content Generation

### 10. Generate Content with AI

**Endpoint:** `POST /api/admin/generate-content`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "fileurl": "https://www.bseindia.com/xml-data/corpfiling/AttachLive/example.pdf",
  "model": "gemini-2.5-flash-lite",
  "pages": "1,3-5,7-9",
  "summary": "Optional: previous summary for context",
  "ai_summary": "Optional: previous AI summary for regeneration",
  "headline": "Optional: previous headline for reference"
}
```

**Request Fields:**
- `fileurl` (required): URL of the PDF file to analyze
- `model` (optional): AI model to use
  - `gemini-2.5-flash-lite` (default, faster)
  - `gemini-2.5-flash-pro` (advanced, slower)
- `pages` (optional): Page specification for extraction
  - Single page: `"5"`
  - Multiple pages: `"1,3,5"`
  - Ranges: `"2-4"`
  - Combinations: `"1,3-6,9-12"`
  - Omit for all pages
- `summary` (optional): Original summary for context
- `ai_summary` (optional): Previous AI summary for regeneration
- `headline` (optional): Previous headline for reference

**Response (200):**
```json
{
  "success": true,
  "category": "Financial Results Announcement",
  "headline": "Company Reports Q3 Financial Results with 25% Revenue Growth",
  "ai_summary": "The company has announced its Q3 financial results showing strong performance with revenue growth of 25% year-over-year. Net profit increased by 18% to $50M. The company maintains positive outlook for Q4 with expected continued growth in key segments. Management highlighted successful product launches and market expansion as key drivers.",
  "sentiment": "Positive",
  "model_used": "gemini-2.5-flash-lite"
}
```

**Example with Page Selection:**
```json
{
  "fileurl": "https://example.com/report.pdf",
  "model": "gemini-2.5-flash-lite",
  "pages": "3-6,9-12"
}
```

**Example with Regeneration Context:**
```json
{
  "fileurl": "https://example.com/report.pdf",
  "model": "gemini-2.5-flash-pro",
  "ai_summary": "Previous summary to improve",
  "headline": "Previous headline to refine"
}
```

**Error Response (400/500):**
```json
{
  "detail": "Failed to download PDF from URL: Connection timeout"
}
```

**Possible Error Messages:**
- `"Invalid page specification: Page numbers must be positive"`
- `"Page numbers [15, 16] exceed document length (10 pages)"`
- `"Failed to download PDF from URL"`
- `"Content generation failed: Model overloaded"`
- `"AI content generation not available - Gemini API key not configured"`

---

## 📊 Statistics

### 11. Get Verification Statistics

**Endpoint:** `GET /api/admin/stats`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "unverified": 145,
  "verified_total": 892,
  "verified_today": 23
}
```

---

## 🔧 Models and Schemas

### GenerateContentRequest
```typescript
{
  fileurl: string;           // Required: PDF URL
  model: string;             // Optional: "gemini-2.5-flash-lite" | "gemini-2.5-flash-pro"
  pages: string | null;      // Optional: "1,3-5,7" format
  summary: string | null;    // Optional: context
  ai_summary: string | null; // Optional: previous AI output
  headline: string | null;   // Optional: previous headline
}
```

### GenerateContentResponse
```typescript
{
  success: boolean;
  category: string;
  headline: string;
  ai_summary: string;
  sentiment: "Positive" | "Negative" | "Neutral";
  model_used: string;
  error: string | null;
}
```

---

## 🐳 Docker Deployment

### Docker Compose Configuration

The service includes a production-ready Docker Compose setup with:
- Optimized Python Alpine image
- Health checks
- Auto-restart policy
- Volume mounting for persistence
- Environment variable injection

### Commands

```bash
# Start service
docker-compose up -d

# View logs
docker-compose logs -f verification-api

# Restart service
docker-compose restart

# Stop service
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

---

## 📖 Usage Examples

### Complete Workflow Example

```bash
# 1. Register an admin user
curl -X POST http://localhost:5002/api/admin/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "SecurePass123!",
    "name": "Admin User"
  }'

# 2. Login to get token
TOKEN=$(curl -X POST http://localhost:5002/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "SecurePass123!"
  }' | jq -r '.access_token')

# 3. Get unverified announcements
curl -X GET "http://localhost:5002/api/admin/announcements?verified=false&limit=5" \
  -H "Authorization: Bearer $TOKEN"

# 4. Generate AI content for an announcement
curl -X POST http://localhost:5002/api/admin/generate-content \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fileurl": "https://www.bseindia.com/xml-data/corpfiling/AttachLive/example.pdf",
    "model": "gemini-2.5-flash-lite",
    "pages": "1,3-5"
  }'

# 5. Update announcement with AI-generated content
curl -X PATCH http://localhost:5002/api/admin/announcements/{corp_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "headline": "AI Generated Headline",
    "category": "Financial Results",
    "ai_summary": "AI generated summary",
    "sentiment": "Positive"
  }'

# 6. Verify the announcement
curl -X POST http://localhost:5002/api/admin/announcements/{corp_id}/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Verified and published"
  }'

# 7. Get statistics
curl -X GET http://localhost:5002/api/admin/stats \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🛠️ Development

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run with auto-reload
python app.py
```

### API Documentation

Once the server is running, access interactive API docs:
- Swagger UI: `http://localhost:5002/docs`
- ReDoc: `http://localhost:5002/redoc`

---

## 🔒 Security Notes

1. **JWT Tokens**: 8-hour expiration, stored in database sessions
2. **Password Hashing**: Bcrypt with salt rounds
3. **CORS**: Configured for production use
4. **Environment Variables**: Never commit `.env` to version control
5. **API Keys**: Rotate Gemini API keys periodically
6. **Database**: Use Supabase service role key only on server-side

---

## 📦 Dependencies

Key dependencies (see `requirements.txt` for full list):
- `fastapi==0.104.1` - Web framework
- `uvicorn==0.24.0` - ASGI server
- `supabase==2.0.3` - Database client
- `python-jose==3.3.0` - JWT handling
- `passlib==1.7.4` - Password hashing
- `google-genai==1.15.0` - Gemini AI
- `PyPDF2==3.0.1` - PDF processing

---

## 🐛 Troubleshooting

### Common Issues

**Issue**: "GENAI_AVAILABLE: False"
- **Solution**: Ensure `google-genai` is installed: `pip install google-genai==1.15.0`

**Issue**: "AI content generation not available"
- **Solution**: Set `GEMINI_API_KEY` in `.env` file

**Issue**: "Failed to download PDF: 403 Forbidden"
- **Solution**: The system includes User-Agent headers for BSE PDFs. Check if PDF URL is accessible.

**Issue**: "Page numbers exceed document length"
- **Solution**: Verify PDF page count and adjust `pages` parameter accordingly

**Issue**: Database connection errors
- **Solution**: Check `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in `.env`

---

## 📄 License

[Add your license information]

## 🤝 Support

For issues and questions:
- Create an issue in the repository
- Contact: [your-email@example.com]

---

**Built with ❤️ using FastAPI, Supabase, and Google Gemini AI**

### Health
- `GET /health` - Health check endpoint

## Database Schema

### Tables Used
1. **admin_users** - Verifier accounts
2. **admin_sessions** - Active login sessions
3. **verification_tasks** - Tasks to verify
4. **verification_edits** - Audit trail of changes
5. **corporatefilings** - Main table with verified announcements

### Key Columns in corporatefilings
- `verified` (boolean) - Is this announcement verified?
- `verified_at` (timestamp) - When was it verified?
- `verified_by` (uuid) - Which verifier approved it?

## Setup

### 1. Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

Required variables:
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Service role key (admin access)
- `JWT_SECRET_KEY` - Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Database Setup

Run the SQL schema in Supabase SQL Editor:
```bash
# Copy contents of schema_updates_simple.sql
# Paste into Supabase SQL Editor
# Execute
```

### 4. Run Application

**Development:**
```bash
python app.py
# or
uvicorn app:app --reload --port 5002
```

**Production:**
```bash
uvicorn app:app --host 0.0.0.0 --port 5002 --workers 4
```

**Docker:**
```bash
docker build -t backfin-verification .
docker run -p 5002:5002 --env-file .env backfin-verification
```

## Usage Workflow

### For Verifiers

1. **Login**
   ```bash
   POST /api/admin/auth/login
   {
     "email": "verifier@example.com",
     "password": "your-password"
   }
   ```
   Response includes `access_token` - use in Authorization header

2. **Claim Task**
   ```bash
   POST /api/admin/tasks/claim
   Authorization: Bearer <your-token>
   ```
   Returns next available task

3. **Edit Task (Optional)**
   ```bash
   PATCH /api/admin/tasks/{task_id}
   Authorization: Bearer <your-token>
   {
     "summary": "Corrected summary",
     "category": "Updated category"
   }
   ```

4. **Verify Task**
   ```bash
   POST /api/admin/tasks/{task_id}/verify
   Authorization: Bearer <your-token>
   {
     "notes": "Verified and approved"
   }
   ```
   This publishes to main `corporatefilings` table

### For Developers

**Check Statistics:**
```bash
GET /api/admin/stats
Authorization: Bearer <your-token>
```

**View Task History:**
```bash
GET /api/admin/tasks/{task_id}
Authorization: Bearer <your-token>
```

## Security

- Passwords hashed with bcrypt
- JWT tokens expire after 8 hours
- Sessions expire after 30 minutes of inactivity
- Service role key for database operations (not exposed to frontend)
- CORS configured for allowed origins only

## Database Functions

### `claim_verification_task(p_user_id, p_session_id)`
Atomically claims a task using `FOR UPDATE SKIP LOCKED` to prevent race conditions.

### `verify_and_publish_task(p_task_id, p_user_id, p_notes)`
Updates `corporatefilings` with verified data and marks task as complete.

### `release_timed_out_tasks(timeout_minutes)`
Background job to release tasks stuck in "in_progress" state.

## Monitoring

- Application logs to stdout (captured by Docker/systemd)
- Health check endpoint at `/health`
- Session tracking in `admin_sessions` table
- Audit trail in `verification_edits` table

## Troubleshooting

**Token expired:**
- Login again to get new token
- Check `ACCESS_TOKEN_EXPIRE_MINUTES` in config

**No tasks available:**
- Check if tasks exist: `SELECT COUNT(*) FROM verification_tasks WHERE status = 'queued'`
- Release timed-out tasks: `SELECT release_timed_out_tasks(30)`

**Database connection failed:**
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
- Check Supabase project status

## Development

**Run tests:**
```bash
pytest tests/
```

**Format code:**
```bash
black app.py auth.py database.py config.py
```

**Type checking:**
```bash
mypy app.py auth.py
```

## Production Deployment

1. Set `PROD=true` in environment
2. Set `DEBUG=false`
3. Configure `CORS_ORIGINS` with actual frontend URLs
4. Use process manager (systemd, supervisor, or Docker)
5. Run behind reverse proxy (nginx/traefik) with HTTPS
6. Set up automated task timeout releases (cron job calling RPC)

## License

Internal tool for Backfin operations.
