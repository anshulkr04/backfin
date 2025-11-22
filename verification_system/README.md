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

## 🔐 Role-Based Access Control

The system supports two user roles:

### Roles

**Verifier (Default)**
- Verify/unverify announcements
- Update announcement details
- View verification queue
- Cannot access review queue

**Admin (Elevated)**
- All verifier permissions
- Access review queue
- Send verified announcements to review
- Approve or reject announcements
- Manage company changes verification
- Apply verified company changes
- View extended statistics

**Note:** New users register as "verifier" by default. To promote a user to admin:
```sql
UPDATE admin_users SET role = 'admin' WHERE email = 'user@example.com';
```

## 📊 Company Database Management

The system includes a comprehensive workflow for managing changes to the `stocklistdata` table. All changes to company data (new listings, ISIN changes, name changes) must be verified before being applied to the production database.

### 🎯 Features
- **Change Detection**: Automatically detect new companies and changes from exchange data
- **Verification Queue**: All changes require admin/verifier approval before application
- **Audit Trail**: Complete logging of all changes with timestamps and user tracking
- **Safe Application**: Atomic operations ensure data integrity
- **Role-Based**: Verifiers can verify, only admins can apply changes

### 📋 Change Types Supported
1. **new** - New company listed on exchange
2. **isin** - ISIN code changed for existing company
3. **name** - Company name changed
4. **both** - Both ISIN and name changed
5. **multiple** - Multiple fields changed

### 🔄 Workflow

```
┌─────────────────────────────────────────────────────────┐
│  1. DETECTION                                           │
│     Exchange Data → detect_changes.py → Detects Changes │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│  2. SUBMISSION                                          │
│     Changes → company_changes_pending table (pending)   │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│  3. VERIFICATION                                        │
│     Admin/Verifier → Reviews → Verify or Reject        │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│  4. APPLICATION (Admin Only)                            │
│     Admin → Apply → Updates stocklistdata table         │
└─────────────────────────┬───────────────────────────────┘
                          │
                   ┌──────▼──────┐
                   │ Audit Trail │
                   └─────────────┘
```

### 🚀 Quick Start

**Step 1: Detect and Submit Changes**
```bash
cd /Users/anshulkumar/backfin/src/services/exchange_data/company_management

# Check current queue statistics
python3 detect_changes.py --stats-only

# Detect and submit changes (completely self-contained!)
python3 detect_changes.py

# The script automatically:
# - Downloads NSE/BSE data from Dhan API
# - Fetches current stocklistdata from Supabase
# - Generates merged stocklist
# - Detects all changes
# - Checks for duplicates (3-layer detection)
# - Submits only new changes to verification queue
# - Cleans up temporary files
# - Provides detailed summary
```

**Step 2: Verify Changes (via API)**
```bash
# Get pending changes
curl -X GET "http://localhost:5002/api/admin/company-changes/pending?page=1" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Verify a change
curl -X POST "http://localhost:5002/api/admin/company-changes/{id}/verify" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Verified from BSE website"}'
```

**Step 3: Apply Changes (Admin Only)**
```bash
# Apply all verified changes
curl -X POST "http://localhost:5002/api/admin/company-changes/apply-verified" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Daily batch application"}'
```

### 📊 API Endpoints Summary

| Endpoint | Method | Access | Description |
|----------|--------|--------|-------------|
| `/api/admin/company-changes/pending` | GET | Admin/Verifier | List pending changes with filters |
| `/api/admin/company-changes/{id}` | GET | Admin/Verifier | Get change detail with audit log |
| `/api/admin/company-changes/{id}/verify` | POST | Admin/Verifier | Verify a change |
| `/api/admin/company-changes/{id}/reject` | POST | Admin/Verifier | Reject a change |
| `/api/admin/company-changes/apply-verified` | POST | Admin Only | Apply verified changes to stocklistdata |
| `/api/admin/company-changes/stats` | GET | Admin/Verifier | Get statistics |

See **🏢 Company Database Management** section below for detailed API documentation with request/response examples.

### ⚙️ Cronjob Setup

The `detect_changes.py` script is completely self-contained, downloads data automatically, and is designed to be cronjob-ready with proper error handling and logging.

**Daily change detection (recommended):**
```bash
# Add to crontab (runs daily at 6 AM) - no arguments needed!
0 6 * * * cd /Users/anshulkumar/backfin/src/services/exchange_data/company_management && /usr/bin/python3 detect_changes.py >> /var/log/company_changes.log 2>&1
```

**Monitor the cronjob:**
```bash
# View log
tail -f /var/log/company_changes.log

# Check statistics
cd /Users/anshulkumar/backfin/src/services/exchange_data/company_management
python3 detect_changes.py --stats-only
```

**Automatic application (optional):**
```bash
# Apply verified changes daily at 8 AM (requires admin token)
0 8 * * * curl -X POST "http://localhost:5002/api/admin/company-changes/apply-verified" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notes":"Automated daily application"}' >> /var/log/company_apply.log 2>&1
```

### 🔒 Safety Features

1. **No Direct Modifications**: Detection script never modifies `stocklistdata` directly
2. **Smart Duplicate Prevention**: 3-layer duplicate detection system
   - Exact match check (same ISIN + same change_type)
   - Same ISIN check (any pending change for that ISIN)
   - Same company check (any pending change for that company_id)
3. **Atomic Application**: Changes applied in database transactions
4. **Complete Audit Trail**: Every action logged with user ID and timestamp
5. **Role-Based Access**: Only admins can apply changes to production
6. **Rollback Support**: Previous values stored for potential rollback
7. **Cronjob Safe**: Proper error handling, exit codes, and logging

### 📈 Monitoring

**Check pending changes:**
```sql
SELECT COUNT(*) FROM company_changes_pending WHERE status = 'pending';
```

**View recent activity:**
```sql
SELECT * FROM company_changes_audit_log 
ORDER BY performed_at DESC LIMIT 20;
```

**Get statistics via API:**
```bash
curl -X GET "http://localhost:5002/api/admin/company-changes/stats" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

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

### 5. Get Announcements (All Categories)

**Endpoint:** `GET /api/admin/announcements`

**Query Parameters:**
- `verified` (boolean): Filter by verification status (default: false)
- `page` (integer): Page number, starts at 1 (default: 1)
- `page_size` (integer): Results per page, max 100 (default: 50)
- `start_date` (string): Filter from date in YYYY-MM-DD format (optional)
- `end_date` (string): Filter to date in YYYY-MM-DD format (optional)
- `category` (string): Filter by specific category (optional)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Example Requests:**
```
# Get first page of unverified announcements
GET /api/admin/announcements?verified=false&page=1&page_size=20

# Get announcements for a specific date range
GET /api/admin/announcements?start_date=2025-11-01&end_date=2025-11-15

# Get announcements filtered by category
GET /api/admin/announcements?category=Board%20Meetings&verified=false

# Combine multiple filters
GET /api/admin/announcements?verified=false&page=2&page_size=50&start_date=2025-11-01&category=Dividends
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
      "date": "2025-11-18T10:00:00"
    }
  ],
  "count": 20,
  "total_count": 1250,
  "total_pages": 63,
  "current_page": 1,
  "page_size": 20,
  "has_next": true,
  "has_previous": false
}
```

### 5a. Get Financial Results Only

**Endpoint:** `GET /api/admin/announcements/financial-results`

**Query Parameters:**
- `verified` (boolean): Filter by verification status (default: false)
- `page` (integer): Page number, starts at 1 (default: 1)
- `page_size` (integer): Results per page, max 100 (default: 50)
- `start_date` (string): Filter from date in YYYY-MM-DD format (optional)
- `end_date` (string): Filter to date in YYYY-MM-DD format (optional)
- `category` (string): Not used in this endpoint (category is fixed to "Financial Results")

**Headers:**
```
Authorization: Bearer <access_token>
```

**Example Request:**
```
GET /api/admin/announcements/financial-results?verified=false&page=1&page_size=25&start_date=2025-11-01
```

**Response (200):**
```json
{
  "announcements": [
    {
      "corp_id": "uuid",
      "category": "Financial Results",
      "headline": "Q3 Results Announcement",
      "ai_summary": "Financial performance summary...",
      "sentiment": "Positive",
      "verified": false,
      "date": "2025-11-15T09:30:00"
    }
  ],
  "count": 25,
  "total_count": 450,
  "total_pages": 18,
  "current_page": 1,
  "page_size": 25,
  "has_next": true,
  "has_previous": false
}
```

### 5b. Get Non-Financial Announcements

**Endpoint:** `GET /api/admin/announcements/non-financial`

**Query Parameters:**
- `verified` (boolean): Filter by verification status (default: false)
- `page` (integer): Page number, starts at 1 (default: 1)
- `page_size` (integer): Results per page, max 100 (default: 50)
- `start_date` (string): Filter from date in YYYY-MM-DD format (optional)
- `end_date` (string): Filter to date in YYYY-MM-DD format (optional)
- `category` (string): Not used in this endpoint (excludes "Financial Results" category)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Description:** Returns all announcements except those in "Financial Results" category (Board Meetings, AGM/EGM, Dividends, etc.)

**Example Request:**
```
GET /api/admin/announcements/non-financial?verified=false&page=1&page_size=30&end_date=2025-11-18
```

**Response (200):**
```json
{
  "announcements": [
    {
      "corp_id": "uuid",
      "category": "Board Meetings",
      "headline": "Board Meeting Scheduled",
      "ai_summary": "Meeting details...",
      "sentiment": "Neutral",
      "verified": false,
      "date": "2025-11-17T14:00:00"
    }
  ],
  "count": 30,
  "total_count": 800,
  "total_pages": 27,
  "current_page": 1,
  "page_size": 30,
  "has_next": true,
  "has_previous": false
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

## 🔍 Review Queue (Admin Only)

### 10. Send Verified Announcement to Review

**Endpoint:** `POST /api/admin/announcements/{corp_id}/send-to-review`

**Authorization:** Admin role required

**Headers:**
```
Authorization: Bearer <admin-token>
```

**Request Body:**
```json
{
  "notes": "Please review the financial numbers"
}
```

**Response (200):**
```json
{
  "success": true,
  "corp_id": "uuid",
  "review_status": "pending_review",
  "sent_to_review_at": "2025-11-21T10:30:00",
  "sent_to_review_by": "admin-uuid",
  "message": "Announcement sent to review queue successfully"
}
```

### 11. Get Review Queue

**Endpoint:** `GET /api/admin/review-queue`

**Authorization:** Admin role required

**Query Parameters:**
- `page` (integer): Page number, starts at 1 (default: 1)
- `page_size` (integer): Results per page, max 100 (default: 50)
- `start_date` (string): Filter from date YYYY-MM-DD (optional)
- `end_date` (string): Filter to date YYYY-MM-DD (optional)
- `category` (string): Filter by category (optional)

**Headers:**
```
Authorization: Bearer <admin-token>
```

**Response (200):**
```json
{
  "announcements": [
    {
      "corp_id": "uuid",
      "headline": "Q3 Financial Results",
      "verified": true,
      "review_status": "pending_review",
      "sent_to_review_at": "2025-11-21T10:30:00",
      "review_notes": "Check financial numbers"
    }
  ],
  "count": 50,
  "total_count": 120,
  "total_pages": 3,
  "current_page": 1,
  "page_size": 50,
  "has_next": true,
  "has_previous": false
}
```

### 12. Review Announcement (Approve/Reject)

**Endpoint:** `POST /api/admin/announcements/{corp_id}/review`

**Authorization:** Admin role required

**Headers:**
```
Authorization: Bearer <admin-token>
```

**Request Body:**
```json
{
  "action": "approve",
  "notes": "Numbers verified from company website"
}
```

**Actions:**
- `"approve"` - Keeps verified status, marks as approved
- `"reject"` - Sends back to verification queue (unverified)

**Response (200):**
```json
{
  "success": true,
  "corp_id": "uuid",
  "action": "approve",
  "review_status": "approved",
  "reviewed_at": "2025-11-21T11:00:00",
  "reviewed_by": "admin-uuid",
  "message": "Announcement approved successfully"
}
```

---

## 🏢 Company Database Management (Admin/Verifier)

### 13. Get Pending Company Changes

**Endpoint:** `GET /api/admin/company-changes/pending`

**Authorization:** Admin or Verifier role required

**Query Parameters:**
- `page` (integer): Page number, starts at 1 (default: 1)
- `page_size` (integer): Results per page, max 100 (default: 50)
- `change_type` (string): Filter by change type (optional: "new", "isin", "name", "both", "multiple")
- `status` (string): Filter by status (default: "pending", options: "pending", "verified", "rejected", "applied")
- `exchange` (string): Filter by exchange (optional: "BSE", "NSE")

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "changes": [
    {
      "id": "uuid",
      "change_type": "new",
      "exchange": "BSE",
      "symbol": "NEWCO",
      "company_name_new": "New Company Limited",
      "isin_new": "INE123A01012",
      "status": "pending",
      "submitted_at": "2025-11-21T10:00:00",
      "submitted_by": "system"
    }
  ],
  "count": 50,
  "total_count": 120,
  "total_pages": 3,
  "current_page": 1,
  "page_size": 50,
  "has_next": true,
  "has_previous": false
}
```

### 14. Get Company Change Detail

**Endpoint:** `GET /api/admin/company-changes/{id}`

**Authorization:** Admin or Verifier role required

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "change": {
    "id": "uuid",
    "change_type": "name",
    "exchange": "BSE",
    "symbol": "OLDCO",
    "company_name_old": "Old Company Limited",
    "company_name_new": "New Company Limited",
    "isin_old": "INE123A01012",
    "isin_new": "INE123A01012",
    "status": "pending",
    "submitted_at": "2025-11-21T10:00:00",
    "submitted_by": "system",
    "verified_at": null,
    "verified_by": null,
    "applied_at": null,
    "applied_by": null
  },
  "audit_log": [
    {
      "id": 1,
      "action": "submitted",
      "performed_at": "2025-11-21T10:00:00",
      "performed_by": "system"
    }
  ]
}
```

### 15. Verify Company Change

**Endpoint:** `POST /api/admin/company-changes/{id}/verify`

**Authorization:** Admin or Verifier role required

**Headers:**
```
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "notes": "Verified from exchange website"
}
```

**Response (200):**
```json
{
  "success": true,
  "id": "uuid",
  "status": "verified",
  "verified_at": "2025-11-21T11:00:00",
  "verified_by": "admin-uuid",
  "message": "Company change verified successfully"
}
```

### 16. Reject Company Change

**Endpoint:** `POST /api/admin/company-changes/{id}/reject`

**Authorization:** Admin or Verifier role required

**Headers:**
```
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "notes": "Invalid ISIN format"
}
```

**Response (200):**
```json
{
  "success": true,
  "id": "uuid",
  "status": "rejected",
  "verified_at": "2025-11-21T11:00:00",
  "verified_by": "admin-uuid",
  "message": "Company change rejected"
}
```

### 17. Apply Verified Changes

**Endpoint:** `POST /api/admin/company-changes/apply-verified`

**Authorization:** Admin role required (elevated privilege)

**Headers:**
```
Authorization: Bearer <admin-token>
```

**Request Body (optional):**
```json
{
  "change_ids": ["uuid1", "uuid2"],
  "notes": "Batch application of verified changes"
}
```

**Note:** If `change_ids` is omitted, all verified changes will be applied.

**Response (200):**
```json
{
  "success": true,
  "applied_count": 5,
  "failed_count": 0,
  "results": [
    {
      "id": "uuid1",
      "success": true,
      "message": "Applied successfully"
    }
  ],
  "message": "Applied 5 company changes successfully"
}
```

### 18. Get Company Changes Statistics

**Endpoint:** `GET /api/admin/company-changes/stats`

**Authorization:** Admin or Verifier role required

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "pending_count": 45,
  "verified_count": 120,
  "rejected_count": 8,
  "applied_count": 112,
  "by_change_type": {
    "new": 30,
    "isin": 15,
    "name": 10,
    "both": 5,
    "multiple": 5
  },
  "by_exchange": {
    "BSE": 40,
    "NSE": 35
  }
}
```

**Full Documentation:** See `/src/services/exchange_data/company_management/README.md` for:
- Change detection workflow
- Database schema details
- Complete usage examples
- Safety features
- Troubleshooting guide

---

## 🤖 AI Content Generation

### 19. Generate Content with AI

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

### 20. Get Verification Statistics

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

# 8. Admin-only: Send to review queue (requires admin role)
curl -X POST http://localhost:5002/api/admin/announcements/{corp_id}/send-to-review \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Please verify the financial figures"
  }'

# 9. Admin-only: Get review queue
curl -X GET http://localhost:5002/api/admin/review-queue \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 10. Admin-only: Approve/reject announcement
curl -X POST http://localhost:5002/api/admin/announcements/{corp_id}/review \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "approve",
    "notes": "Verified from company website"
  }'
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

1. **JWT Tokens**: 8-hour expiration, stored in database sessions, includes user role
2. **Password Hashing**: Bcrypt with salt rounds
3. **Role-Based Access**: Admin endpoints protected by role validation
4. **CORS**: Configured for production use
5. **Environment Variables**: Never commit `.env` to version control
6. **API Keys**: Rotate Gemini API keys periodically
7. **Database**: Use Supabase service role key only on server-side
8. **Audit Logging**: All verification actions tracked in audit log

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

## 💾 Database Setup

### Initial Schema

Run in Supabase SQL Editor:

```sql
-- Create admin_users table
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT DEFAULT 'verifier' CHECK (role IN ('admin', 'verifier')),
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

-- Add verification columns to corporatefilings
ALTER TABLE corporatefilings 
ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS verified_by UUID REFERENCES admin_users(id);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_admin_sessions_user_id ON admin_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_token ON admin_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_corporatefilings_verified ON corporatefilings(verified);
```

### Role-Based Review System Migration

To enable the review queue feature, run the SQL migration:

```bash
# Execute in Supabase SQL Editor
# File: verification_system/ROLE_BASED_REVIEW_SYSTEM.sql
```

This adds:
- Review status tracking columns to `corporatefilings`
- `verification_audit_log` table for audit trail
- Admin-only review queue views
- Approve/reject workflow

### Company Management System Migration

To enable company database change verification, run the SQL migration:

```bash
# Execute in Supabase SQL Editor
# File: src/services/exchange_data/company_management/COMPANY_VERIFICATION_SCHEMA.sql
```

This adds:
- `company_changes_pending` table for pending changes
- `company_changes_audit_log` table for audit trail
- `apply_company_change()` function for applying verified changes
- Views for verification queue, ready-to-apply, and statistics
- Complete workflow for new companies and existing company changes

**Important:** Run both migrations in order:
1. ROLE_BASED_REVIEW_SYSTEM.sql (for roles and review queue)
2. COMPANY_VERIFICATION_SCHEMA.sql (for company change management)

---

**Built with ❤️ using FastAPI, Supabase, and Google Gemini AI**
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
