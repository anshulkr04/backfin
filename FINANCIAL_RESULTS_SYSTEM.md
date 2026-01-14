# Financial Results Verification System

## Overview

The financial results verification system enables tracking, verification, and querying of financial data extracted from corporate announcements. Financial results are automatically verified when their parent announcement is verified through the verification system.

---

## Database Schema

### Migration

Run the migration script to add verification tracking to the `financial_results` table:

```bash
# Execute the SQL migration in Supabase SQL Editor
/scripts/migrations/add_financial_results_verification.sql
```

### New Columns

| Column | Type | Description |
|--------|------|-------------|
| `verified` | BOOLEAN | Indicates if the financial result has been verified (default: false) |
| `verified_at` | TIMESTAMPTZ | Timestamp when the financial result was verified |
| `verified_by` | UUID | Reference to admin_users.id who verified this result |

### Indexes

- `idx_financial_results_verified` - Fast queries on verification status
- `idx_financial_results_verified_corp_id` - Composite index for verified + corp_id
- `idx_financial_results_company_id` - Fast filtering by company
- `idx_financial_results_symbol` - Fast filtering by symbol
- `idx_financial_results_isin` - Fast filtering by ISIN

### Database Trigger

**Auto-Verification Trigger:**
When an announcement in `corporatefilings` is verified/unverified, the associated financial results are automatically updated with the same verification status.

```sql
-- Trigger: trigger_auto_verify_financial_results
-- Fires on UPDATE of verified column in corporatefilings
-- Automatically updates financial_results.verified, verified_at, verified_by
```

---

## API Endpoints

### 1. Get Financial Results (Public API)

**Endpoint:** `GET /api/financial_results`

**Description:** Retrieve verified financial results with comprehensive filters

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string | No | - | Filter results from this date (YYYY-MM-DD) |
| `end_date` | string | No | - | Filter results up to this date (YYYY-MM-DD) |
| `company_id` | integer | No | - | Filter by company ID |
| `symbol` | string | No | - | Filter by stock symbol (e.g., "RELIANCE") |
| `isin` | string | No | - | Filter by ISIN code (e.g., "INE002A01018") |
| `verified` | boolean | No | true | Show only verified results (true) or unverified (false) |
| `page` | integer | No | 1 | Page number for pagination |
| `page_size` | integer | No | 20 | Results per page (max: 100) |

**Example Requests:**

```bash
# Get all verified financial results
GET /api/financial_results

# Get financial results for specific company by symbol
GET /api/financial_results?symbol=RELIANCE&verified=true

# Get financial results by ISIN with date range
GET /api/financial_results?isin=INE002A01018&start_date=2025-01-01&end_date=2025-12-31

# Get unverified financial results (for admin review)
GET /api/financial_results?verified=false&page=1&page_size=50
```

**Response (200):**

```json
{
  "count": 20,
  "total_count": 145,
  "total_pages": 8,
  "current_page": 1,
  "page_size": 20,
  "has_next": true,
  "has_previous": false,
  "financial_results": [
    {
      "id": "uuid",
      "corp_id": "announcement-uuid",
      "company_id": 12345,
      "symbol": "RELIANCE",
      "isin": "INE002A01018",
      "period": "Q3 FY24",
      "sales_current": "₹2,50,000 Cr",
      "sales_previous_year": "₹2,00,000 Cr",
      "pat_current": "₹15,000 Cr",
      "pat_previous": "₹12,000 Cr",
      "sales_yoy": "25% YoY",
      "pat_yoy": "25% YoY",
      "fileurl": "https://...",
      "verified": true,
      "verified_at": "2026-01-14T10:30:00Z",
      "verified_by": "admin-uuid",
      "corporatefilings": {
        "date": "2026-01-10T09:00:00Z",
        "company_name": "Reliance Industries Limited",
        "headline": "Q3 FY24 Financial Results",
        "category": "Financial Results",
        "ai_summary": "Strong quarter with..."
      }
    }
  ]
}
```

---

## Verification System Integration

### Verification Workflow

1. **Scraper Stage:** Financial results are created with `verified: false`
2. **Admin Review:** Verifiers review announcements in verification system
3. **Verification:** When announcement is verified, financial results are auto-verified
4. **Public API:** Only verified financial results are shown by default

### Verification System Endpoints

#### Verify Announcement (Auto-verifies Financial Results)

**Endpoint:** `POST /api/verification/announcements/{corp_id}/verify`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Behavior:**
- Marks announcement as verified
- **Automatically verifies** associated financial results
- Sets verification timestamp and verifier ID on both tables

**Response (200):**
```json
{
  "success": true,
  "corp_id": "uuid",
  "verified_at": "2026-01-14T10:30:00Z",
  "verified_by": "admin-uuid",
  "message": "Announcement verified successfully"
}
```

#### Unverify Announcement (Auto-unverifies Financial Results)

**Endpoint:** `POST /api/verification/announcements/{corp_id}/unverify`

**Behavior:**
- Marks announcement as unverified
- **Automatically unverifies** associated financial results
- Clears verification metadata on both tables

---

## CRUD Operations on Financial Results

### Get Financial Result by Corp ID

**Endpoint:** `GET /api/verification/financial-results/{corp_id}`

**Description:** Fetch financial result for specific announcement

### Create Financial Result

**Endpoint:** `POST /api/verification/financial-results`

**Request Body:**
```json
{
  "corp_id": "announcement-uuid",
  "period": "Q3 FY24",
  "sales_current": "₹2,50,000 Cr",
  "sales_previous_year": "₹2,00,000 Cr",
  "pat_current": "₹15,000 Cr",
  "pat_previous": "₹12,000 Cr",
  "sales_yoy": "25% YoY",
  "pat_yoy": "25% YoY"
}
```

### Update Financial Result

**Endpoint:** `PATCH /api/verification/financial-results/{id}`

**Request Body:**
```json
{
  "sales_current": "₹2,51,000 Cr",
  "pat_current": "₹15,200 Cr"
}
```

### Delete Financial Result

**Endpoint:** `DELETE /api/verification/financial-results/{id}`

**Auth Required:** Admin only

---

## Scraper Integration

### BSE Scraper

**File:** `/src/scrapers/bse_scraper.py`

**Function:** `safely_upload_financial_data()`

**Behavior:**
- Extracts financial data from AI summary
- Sets `verified: false` by default
- Uploads to `financial_results` table
- Handles duplicates and updates missing fields

### NSE Scraper

**File:** `/src/scrapers/nse_scraper.py`

**Function:** `safely_upload_financial_data()`

**Behavior:** Same as BSE scraper

---

## Database Views

### financial_results_unverified

View of all unverified financial results with announcement metadata.

```sql
SELECT * FROM financial_results_unverified;
```

### financial_results_verified

View of all verified financial results with verifier information.

```sql
SELECT * FROM financial_results_verified;
```

---

## Example Use Cases

### 1. Get Latest Verified Financial Results

```bash
curl "https://api.backfin.com/api/financial_results?page=1&page_size=10&verified=true"
```

### 2. Get Financial Results for Specific Company

```bash
curl "https://api.backfin.com/api/financial_results?symbol=RELIANCE&verified=true"
```

### 3. Get Unverified Results for Admin Review

```bash
curl -H "Authorization: Bearer <token>" \
  "https://api.backfin.com/api/financial_results?verified=false"
```

### 4. Filter by Date Range

```bash
curl "https://api.backfin.com/api/financial_results?start_date=2025-10-01&end_date=2025-12-31"
```

### 5. Verify Announcement (Auto-verifies Financial Data)

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  "https://api.backfin.com/api/verification/announcements/{corp_id}/verify"
```

---

## Testing

### 1. Run Migration

```sql
-- In Supabase SQL Editor
\i scripts/migrations/add_financial_results_verification.sql
```

### 2. Verify Trigger Works

```sql
-- Update announcement to verified
UPDATE corporatefilings 
SET verified = true, 
    verified_at = NOW(), 
    verified_by = '<admin_uuid>'
WHERE corp_id = '<test_corp_id>';

-- Check if financial results were auto-verified
SELECT verified, verified_at, verified_by 
FROM financial_results 
WHERE corp_id = '<test_corp_id>';
```

### 3. Test API Endpoint

```bash
# Test public API
curl "http://localhost:5001/api/financial_results?verified=true"

# Test with filters
curl "http://localhost:5001/api/financial_results?symbol=RELIANCE&start_date=2025-01-01"
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Scraper Layer                            │
│  (BSE/NSE Scrapers)                                             │
│  - Extract financial data from PDFs                             │
│  - Set verified = false                                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Database Layer                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ corporatefilings                 financial_results      │   │
│  │ ─────────────────               ─────────────────       │   │
│  │ corp_id (PK)                    corp_id (FK)            │   │
│  │ verified                        verified                │   │
│  │ verified_at                     verified_at             │   │
│  │ verified_by                     verified_by             │   │
│  └────────┬────────────────────────────────┬───────────────┘   │
│           │                                 │                   │
│           │  ┌──────────────────────────────┘                   │
│           │  │  Trigger: auto_verify_financial_results          │
│           │  │  ON UPDATE OF verified                           │
│           └──┼──► Auto-updates financial_results.verified       │
│              │                                                   │
└──────────────┼───────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Verification System                             │
│  /api/verification/announcements/{id}/verify                    │
│  - Verifies announcement                                        │
│  - Trigger auto-verifies financial results                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Public API                                  │
│  GET /api/financial_results                                     │
│  - Returns only verified results by default                     │
│  - Supports filtering by company, date, ISIN, symbol           │
│  - Pagination support                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Security Considerations

1. **Default Verified Filter:** Public API shows only verified results by default
2. **Admin Access Required:** Unverified results require authentication
3. **Audit Logging:** All verification actions are logged in `verification_audit_log`
4. **Foreign Key Constraints:** Ensures data integrity with admin_users table

---

## Maintenance

### Check Verification Status

```sql
-- Count verified vs unverified
SELECT 
  verified,
  COUNT(*) as count
FROM financial_results
GROUP BY verified;
```

### Find Orphaned Financial Results

```sql
-- Financial results without parent announcement
SELECT fr.* 
FROM financial_results fr
LEFT JOIN corporatefilings cf ON fr.corp_id = cf.corp_id
WHERE cf.corp_id IS NULL;
```

### Bulk Verify by Company

```sql
-- Verify all financial results for a specific company
UPDATE financial_results
SET 
  verified = true,
  verified_at = NOW(),
  verified_by = '<admin_uuid>'
WHERE company_id = <company_id> AND verified = false;
```

---

## Support

For issues or questions:
- Check logs: `logs/system/`
- Review audit trail: `verification_audit_log` table
- Database views: `financial_results_unverified`, `financial_results_verified`
