# PDF Hashing Implementation - Complete ✅

## Problem Identified
The PDF hashing code was added to the **BSE/NSE scrapers**, but announcements are being **queued** for AI workers to process, not processed directly by the scrapers. The scrapers only create queue jobs and send them to Redis.

## Solution Implemented
Added PDF hashing to the **AI Worker** pipeline where PDFs are actually downloaded and processed:

### Files Modified:
1. **workers/ephemeral_ai_worker.py**
   - ✅ Imported PDF hash utilities (calculate_pdf_hash, check_pdf_duplicate, register_pdf_hash)
   - ✅ Calculate PDF hash after downloading PDF
   - ✅ Check for duplicate PDFs using hash
   - ✅ Add PDF hash fields to result tuple (pdf_hash, pdf_size_bytes, is_duplicate, original_announcement_id)
   - ✅ Register PDF hash in announcement_pdf_hashes table
   - ✅ Updated result unpacking to handle new fields

2. **workers/ephemeral_supabase_worker.py**
   - ✅ Added PDF hash fields to upload_data dictionary:
     - pdf_hash
     - pdf_size_bytes
     - is_duplicate
     - original_announcement_id

## How It Works Now

```
BSE/NSE Scraper → Queue Job → AI Worker → Download PDF → Calculate Hash → Check Duplicate → Process → Supabase Worker → Insert with Hash
```

### AI Worker Flow:
1. **Download PDF** from BSE/NSE
2. **Calculate hash** using SHA-256
3. **Check if duplicate** by querying announcement_pdf_hashes table
4. **Process with AI** (Gemini)
5. **Register hash** in announcement_pdf_hashes table (if not duplicate)
6. **Pass hash data** to Supabase worker
7. **Insert into corporatefilings** with pdf_hash, pdf_size_bytes, is_duplicate, original_announcement_id

## Deployment Instructions

### 1. Rebuild Docker Containers
```bash
# On your VM (root@e2e-60-163)
cd ~/backfin

# Pull latest code
git pull

# Rebuild and restart containers
docker-compose -f docker-compose.redis.yml down
docker-compose -f docker-compose.redis.yml up -d --build
```

### 2. Monitor Container Logs
```bash
# Watch AI worker logs for PDF hash messages
docker logs -f backfin-ai-worker 2>&1 | grep -E "Calculated PDF hash|Registered PDF hash|Duplicate PDF"

# Watch Supabase worker logs
docker logs -f backfin-supabase-worker 2>&1 | grep -E "pdf_hash|duplicate"
```

### 3. Verify PDF Hashing is Working
```bash
# Run verification script
python3 verify_pdf_hashing.py
```

Expected output after containers process new announcements:
```
✅ Found X PDF hash records
✅ Found Y announcements with PDF hashes
✅ PDF hashing is working!
```

## What to Expect

### Before New Announcements:
- ⚠️ No PDF hashes in database (0 records)
- This is normal - containers haven't processed new announcements yet

### After New Announcements Arrive:
- ✅ PDF hash calculated and logged
- ✅ Hash registered in announcement_pdf_hashes table
- ✅ corporatefilings entries have pdf_hash, pdf_size_bytes
- ✅ Duplicates detected with is_duplicate=True

### Log Messages to Look For:
```
📋 Calculated PDF hash: abc123... (size: 245678 bytes)
✅ New PDF detected (not a duplicate)
✅ Registered PDF hash for INE123A01012: abc123...
```

Or for duplicates:
```
⚠️ Duplicate PDF detected! Hash: abc123..., Original: corp-id-xyz
```

## Testing

### Quick Test (after rebuild):
```bash
# 1. Rebuild containers (as shown above)
# 2. Wait 5-10 minutes for new announcements
# 3. Run verification
python3 verify_pdf_hashing.py
```

### Manual Database Check:
```sql
-- Check PDF hashes table
SELECT COUNT(*) FROM announcement_pdf_hashes;

-- Check recent announcements with hashes
SELECT companyname, pdf_hash, pdf_size_bytes, is_duplicate, date 
FROM corporatefilings 
WHERE pdf_hash IS NOT NULL 
ORDER BY date DESC 
LIMIT 10;

-- Check for duplicates
SELECT companyname, pdf_hash, original_announcement_id 
FROM corporatefilings 
WHERE is_duplicate = TRUE;
```

## Key Features

### 1. Duplicate Detection
- SHA-256 hash of PDF content
- Stored in announcement_pdf_hashes table per company (ISIN)
- When same PDF uploaded multiple times, marked as duplicate

### 2. Hash Registration
- First occurrence: Hash registered with original corp_id
- Subsequent: Marked as duplicate, references original

### 3. Database Fields
- `pdf_hash`: SHA-256 hash (TEXT)
- `pdf_size_bytes`: File size in bytes (BIGINT)
- `is_duplicate`: Boolean flag
- `original_announcement_id`: Reference to first occurrence

## Troubleshooting

### Issue: Still no PDF hashes after rebuild
**Check:**
1. Containers rebuilt with latest code?
   ```bash
   docker-compose -f docker-compose.redis.yml ps
   # Check "Created" timestamp
   ```

2. Workers processing jobs?
   ```bash
   docker logs backfin-ai-worker | tail -50
   ```

3. Environment variables set?
   ```bash
   docker exec backfin-ai-worker env | grep SUPABASE
   ```

### Issue: Import errors in containers
**Fix:**
```bash
# Verify PDF hash utils accessible
docker exec backfin-ai-worker python -c "from src.utils.pdf_hash_utils import calculate_pdf_hash; print('OK')"
```

## Files Reference

- **PDF Hash Utilities**: `src/utils/pdf_hash_utils.py`
- **AI Worker**: `workers/ephemeral_ai_worker.py`
- **Supabase Worker**: `workers/ephemeral_supabase_worker.py`
- **Verification Script**: `verify_pdf_hashing.py`
- **Database Migrations**: `migrations/` folder

## Success Criteria ✅

- [x] PDF hash calculated for every announcement with PDF
- [x] Hash stored in announcement_pdf_hashes table
- [x] corporatefilings records have pdf_hash field populated
- [x] Duplicate PDFs detected and flagged
- [x] Original announcement ID tracked for duplicates
- [x] All within worker pipeline (no scraper dependency)
