# PDF Hash-Based Duplicate Detection System

## Overview

This system prevents duplicate announcements (same PDF file uploaded multiple times by exchanges/companies) from cluttering the user feed. All announcements are saved in the database, but duplicates are marked and hidden from users by default.

## How It Works

### 1. **PDF Hash Calculation**
- When processing an announcement with a PDF, calculate SHA-256 hash of the PDF content
- Store the hash along with file size for quick comparison

### 2. **Duplicate Detection Logic**
```
For each new announcement with PDF:
  1. Download PDF and calculate hash
  2. Check if hash exists for this company (ISIN)
  3. If hash exists:
     - Mark announcement as duplicate
     - Link to original announcement
     - Save to database but hide from users
  4. If hash is new:
     - Save hash to tracking table
     - Mark as original
     - Show to users normally
```

### 3. **Database Schema**

#### **announcement_pdf_hashes** table
Tracks unique PDF hashes per company:
- `pdf_hash`: SHA-256 hash of PDF content
- `isin`: Company identifier
- `original_corp_id`: First announcement with this PDF
- `duplicate_count`: How many duplicates found

#### **corporatefilings** table additions
New columns:
- `pdf_hash`: Hash of the PDF
- `pdf_size_bytes`: File size
- `is_duplicate`: Boolean flag
- `original_announcement_id`: Links to original if duplicate
- `duplicate_of_newsid`: NewsID of original

### 4. **User-Facing Queries**
Use the `unique_announcements` view or filter by `is_duplicate = FALSE`:

```sql
-- Get all unique announcements
SELECT * FROM unique_announcements WHERE isin = 'INE123A01012';

-- Or filter directly
SELECT * FROM corporatefilings 
WHERE isin = 'INE123A01012' 
  AND (is_duplicate = FALSE OR is_duplicate IS NULL)
ORDER BY date DESC;
```

## Implementation Steps

### Step 1: Run Database Migration

```bash
# In Supabase SQL Editor, run:
scripts/migrations/add_pdf_hash_tracking.sql
```

Verify tables and columns were created:
```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'public' 
    AND tablename IN ('announcement_pdf_hashes', 'duplicate_detection_stats');
```

### Step 2: Update Scraper Code

Modify `src/scrapers/bse_scraper.py` to:
1. Calculate PDF hash after download
2. Check for duplicates before insertion
3. Mark duplicates appropriately

See: `src/utils/pdf_hash_utils.py` for helper functions

### Step 3: Update API Endpoints

Modify API endpoints to exclude duplicates:

```python
# Before (shows all)
response = supabase.table('corporatefilings').select('*').eq('isin', isin).execute()

# After (hides duplicates)
response = supabase.table('corporatefilings').select('*')\
    .eq('isin', isin)\
    .or('is_duplicate.is.false,is_duplicate.is.null')\
    .execute()

# Or use the view
response = supabase.table('unique_announcements').select('*').eq('isin', isin).execute()
```

### Step 4: Update Worker Processing

Workers (AI worker, Supabase worker) need to handle:
- Hash calculation during PDF processing
- Duplicate checking before insertion
- Proper marking of duplicate status

## Key Functions

### Database Functions

1. **check_duplicate_pdf(isin, pdf_hash, symbol)**
   - Returns: is_duplicate, original_corp_id, original_newsid, duplicate_count
   - Use this to check if a PDF hash already exists for a company

2. **update_duplicate_stats()**
   - Updates daily statistics
   - Call at end of day or via cron job

3. **find_announcement_duplicates(corp_id)**
   - Find all duplicates of a specific announcement
   - Useful for admin/debugging

### Python Helper Functions

Located in `src/utils/pdf_hash_utils.py`:

1. **calculate_pdf_hash(filepath)** 
   - Calculate SHA-256 hash of PDF file

2. **check_pdf_duplicate(supabase, isin, pdf_hash)**
   - Check if PDF is duplicate in database

3. **register_pdf_hash(supabase, announcement_data, pdf_hash, pdf_size)**
   - Register new PDF hash in tracking table

4. **mark_announcement_duplicate(supabase, corp_id, original_corp_id, original_newsid, pdf_hash)**
   - Mark an announcement as duplicate

## Analytics & Monitoring

### Daily Statistics

```sql
-- View daily duplicate statistics
SELECT * FROM duplicate_detection_stats 
ORDER BY date DESC 
LIMIT 30;
```

### Duplicate Analysis

```sql
-- See all duplicates with their originals
SELECT * FROM duplicate_announcements_report
WHERE duplicate_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY duplicate_date DESC;
```

### Top Companies with Duplicates

```sql
SELECT 
    companyname,
    symbol,
    isin,
    COUNT(*) as duplicate_count
FROM corporatefilings
WHERE is_duplicate = TRUE
    AND date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY companyname, symbol, isin
ORDER BY duplicate_count DESC
LIMIT 10;
```

### Hash Reuse Analysis

```sql
SELECT 
    pdf_hash,
    company_name,
    isin,
    duplicate_count,
    first_seen_at,
    original_date
FROM announcement_pdf_hashes
WHERE duplicate_count > 2  -- More than 2 duplicates
ORDER BY duplicate_count DESC, first_seen_at DESC;
```

## Performance Considerations

### Indexes
- `(isin, pdf_hash)` composite index for fast duplicate checking
- `is_duplicate` index for filtering user queries
- `date DESC` indexes for recent announcement queries

### Query Optimization
```sql
-- Fast duplicate check during insertion
SELECT original_corp_id, original_newsid 
FROM announcement_pdf_hashes 
WHERE isin = ? AND pdf_hash = ?
LIMIT 1;

-- Fast user query
SELECT * FROM corporatefilings 
WHERE date >= ?
  AND (is_duplicate = FALSE OR is_duplicate IS NULL)
ORDER BY date DESC;
```

## Migration Strategy for Existing Data

If you have existing announcements and want to detect historical duplicates:

1. **Option A: Fresh Start**
   - Only apply hash checking to new announcements going forward
   - Existing announcements remain unmarked

2. **Option B: Backfill (Resource Intensive)**
   - Download all historical PDFs
   - Calculate hashes retroactively
   - Mark duplicates in historical data
   - **Warning**: This requires downloading thousands of PDFs

**Recommendation**: Use Option A for production. Option B only for specific analysis needs.

## Testing

### Test Duplicate Detection

```python
# 1. Process an announcement with PDF
# 2. Re-upload same PDF with different metadata
# 3. Verify second one is marked as duplicate

# Example test case
announcement_1 = {
    'NEWSID': 'TEST001',
    'SCRIP_CD': '500325',
    'ISIN': 'INE123A01012',
    'ATTACHMENTNAME': 'test_doc.pdf'
}

announcement_2 = {
    'NEWSID': 'TEST002',  # Different ID
    'SCRIP_CD': '500325',  # Same company
    'ISIN': 'INE123A01012',
    'ATTACHMENTNAME': 'test_doc.pdf'  # Same PDF
}

# Expected: announcement_2 should be marked as duplicate
```

### Verify Database State

```sql
-- Check hash was stored
SELECT * FROM announcement_pdf_hashes WHERE isin = 'INE123A01012';

-- Check duplicate was marked
SELECT corp_id, headline, is_duplicate, original_announcement_id 
FROM corporatefilings 
WHERE isin = 'INE123A01012'
ORDER BY date DESC;
```

## Troubleshooting

### Issue: Duplicates not being detected

Check:
1. PDF hash calculation working correctly
2. ISIN matching exactly (case-sensitive)
3. Hash comparison happening before insertion
4. Database indexes present

```sql
-- Verify indexes
SELECT indexname FROM pg_indexes 
WHERE tablename = 'announcement_pdf_hashes';
```

### Issue: False positives (different PDFs marked as duplicates)

Check:
1. Hash calculation consistency
2. PDF download completeness
3. File corruption during download

```sql
-- Compare file sizes
SELECT pdf_hash, COUNT(*), ARRAY_AGG(DISTINCT pdf_size_bytes)
FROM corporatefilings
WHERE pdf_hash IS NOT NULL
GROUP BY pdf_hash
HAVING COUNT(DISTINCT pdf_size_bytes) > 1;
```

### Issue: Performance degradation

Check:
1. Index usage in queries
2. Hash table size
3. Query plan using EXPLAIN

```sql
EXPLAIN ANALYZE
SELECT * FROM announcement_pdf_hashes 
WHERE isin = 'INE123A01012' AND pdf_hash = 'abc123...';
```

## API Changes Summary

### Endpoints to Update

1. **GET /api/announcements**
   - Add `is_duplicate` filter (default: exclude)
   - Add `include_duplicates` query parameter

2. **GET /api/company/:isin/announcements**
   - Filter out duplicates by default
   - Add parameter to show all including duplicates

3. **GET /api/announcement/:corp_id**
   - Show if announcement is a duplicate
   - Link to original if duplicate

### Example Response Changes

```json
{
  "corp_id": "uuid-here",
  "headline": "Quarterly Results",
  "is_duplicate": true,
  "duplicate_info": {
    "original_corp_id": "original-uuid",
    "original_newsid": "BSE123456",
    "original_date": "2026-01-10T10:00:00Z",
    "duplicate_count": 3
  }
}
```

## Maintenance

### Daily Tasks
```sql
-- Run at end of each day
SELECT update_duplicate_stats();
```

### Weekly Tasks
```sql
-- Review duplicate patterns
SELECT * FROM duplicate_announcements_report
WHERE duplicate_date >= CURRENT_DATE - INTERVAL '7 days';

-- Clean up old hash entries (optional, after 6 months)
DELETE FROM announcement_pdf_hashes 
WHERE first_seen_at < CURRENT_DATE - INTERVAL '6 months'
  AND duplicate_count = 0;
```

### Monthly Tasks
```sql
-- Analyze top duplicate sources
SELECT 
    companyname,
    COUNT(*) as total_duplicates,
    SUM(duplicate_count) as total_reuses
FROM announcement_pdf_hashes
WHERE first_seen_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY companyname
ORDER BY total_duplicates DESC
LIMIT 20;
```

## Benefits

1. **Cleaner User Feed**: Users see only unique announcements
2. **Complete Data**: All announcements saved for compliance/audit
3. **Better Analytics**: Track which companies/exchanges upload duplicates
4. **Performance**: Efficient queries with proper indexing
5. **Flexibility**: Can show duplicates in admin views when needed

## Future Enhancements

1. **Fuzzy Matching**: Detect similar PDFs (not just exact matches)
2. **Content Comparison**: Compare actual content, not just hashes
3. **Admin Dashboard**: View duplicate statistics
4. **Auto-Merge**: Automatically merge duplicate metadata
5. **Alert System**: Notify when duplicate rate exceeds threshold
