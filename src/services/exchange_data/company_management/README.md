# Company Database Management System

## Overview

This system manages the verification workflow for changes to the `stocklistdata` table. Any new companies or changes to existing companies must be verified by an admin/verifier before being applied to the production database.

## Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    1. DETECTION PHASE                                │
│  Exchange Data (NSE/BSE) → Compare → Detect Changes → CSV Output    │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    2. SUBMISSION PHASE                               │
│  CSV Changes → Parse → Submit to company_changes_pending Table      │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   3. VERIFICATION PHASE                              │
│  Admin/Verifier Reviews → Approve/Reject Each Change                │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    4. APPLICATION PHASE                              │
│  Verified Changes → Apply to stocklistdata Table (Admin Only)       │
└─────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
company_management/
├── detect_changes.py      # Self-contained main script (downloads, processes, submits)
├── cronjob_examples.txt   # Sample crontab configurations
├── README.md              # This file
└── __init__.py            # Package initialization
```

**Key Features:**
- ✅ **Self-Contained**: No dependencies on external folders
- ✅ **Auto-Downloads**: Fetches NSE/BSE data from Dhan API automatically
- ✅ **Auto-Cleanup**: Removes temporary files after completion
- ✅ **Database Integration**: Fetches current data from Supabase
- ✅ **Smart Detection**: Compares and detects all types of changes
- ✅ **Duplicate Prevention**: 3-layer duplicate checking system

**Note:** The database schema is managed by the verification system. See `/verification_system/` for API setup.

## Database Schema

### Main Tables

#### 1. `company_changes_pending`
Stores all detected changes awaiting verification.

**Key Columns:**
- `id`: UUID primary key
- `isin`: Company ISIN code
- `change_type`: Type of change (new, isin, name, bsecode, nsecode, etc.)
- `new_*`: Proposed new values
- `old_*`: Current values in stocklistdata
- `company_id`: Existing company ID (NULL for new companies)
- `verified`: Boolean flag
- `verified_by`: Admin/verifier user ID
- `review_status`: pending | approved | rejected | needs_review
- `applied`: Boolean flag indicating if applied to stocklistdata
- `applied_at`: Timestamp when applied

#### 2. `company_changes_audit_log`
Tracks all actions on company changes for audit purposes.

#### 3. Views
- `company_verification_queue`: Unverified changes
- `company_changes_ready_to_apply`: Verified but not applied
- `company_changes_stats`: Statistics summary

### Change Types

- `new`: Completely new company
- `isin`: ISIN code changed
- `name`: Company name changed
- `bsecode`: BSE code changed
- `nsecode`: NSE code changed
- `symbol`: Symbol changed
- `securityid`: Security ID changed
- `sector`: Sector changed
- `multiple`: Multiple fields changed (comma-separated)

## Setup

### 1. Database Setup

The database schema is managed by the verification system. See `/verification_system/README.md` for:
- Database schema setup
- API endpoint configuration  
- Admin user creation

### 2. Install Python Dependencies

```bash
pip install pandas numpy supabase python-dotenv
```

### 3. Configure Environment Variables

Add to `.env`:
```env
SUPABASE_URL2=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

## Usage

### Step 1: Detect and Submit Changes

Run the detection script (completely self-contained):

```bash
cd /Users/anshulkumar/backfin/src/services/exchange_data/company_management

# Standard run (does everything automatically)
python3 detect_changes.py

# Check statistics only (no detection)
python3 detect_changes.py --stats-only

# Keep downloaded files for inspection (debugging)
python3 detect_changes.py --keep-files

# Direct execution (file is executable)
./detect_changes.py
```

**What it does automatically:**
1. 📥 Downloads latest NSE and BSE data from Dhan API
2. 📊 Fetches current stocklistdata from Supabase database
3. 🔄 Generates merged stocklist (combines NSE + BSE with priority logic)
4. 🔍 Compares and detects all changes (new companies, ISIN changes, name changes, etc.)
5. ✅ Checks for duplicates (3-layer detection: exact match, same ISIN, same company)
6. 📤 Submits only new changes to `company_changes_pending` table
7. 🧹 Cleans up all temporary files (unless --keep-files used)
8. 📝 Provides detailed summary with statistics

**Output:**
```
=== DETECTION PHASE ===
Found 50 exact ISIN matches
Detected changes in 12 records
Found 5 new companies

=== SUBMISSION PHASE ===
✅ Submitted: ISIN INE123A01012 (name)
✅ Submitted: ISIN INE456B01023 (new)
⏭️  Skipping duplicate: ISIN INE789C01034 (bsecode)

SUBMISSION SUMMARY:
Total changes detected:     17
Successfully submitted:     15
Skipped (duplicates):       2
Errors:                     0
```

### Step 2: Verify Changes (Admin/Verifier)

Access the verification API to review and approve changes.

#### Get Pending Changes

```bash
GET /api/admin/company-changes/pending?page=1&page_size=50
Authorization: Bearer <token>
```

**Response:**
```json
{
  "changes": [
    {
      "id": "uuid",
      "isin": "INE123A01012",
      "change_type": "name",
      "new_name": "NEW COMPANY NAME LTD",
      "old_name": "Old Company Name Ltd",
      "company_id": "uuid",
      "verified": false,
      "detected_at": "2025-11-21T10:00:00"
    }
  ],
  "total_count": 15,
  "current_page": 1
}
```

#### Get Change Details

```bash
GET /api/admin/company-changes/{change_id}
Authorization: Bearer <token>
```

#### Verify a Change

```bash
POST /api/admin/company-changes/{change_id}/verify
Authorization: Bearer <token>
Content-Type: application/json

{
  "notes": "Verified from NSE website"
}
```

#### Reject a Change

```bash
POST /api/admin/company-changes/{change_id}/reject
Authorization: Bearer <token>
Content-Type: application/json

{
  "action": "reject",
  "notes": "Incorrect data, needs correction"
}
```

### Step 3: Apply Verified Changes (Admin Only)

Once changes are verified, admin can apply them to stocklistdata:

```bash
POST /api/admin/company-changes/apply-verified
Authorization: Bearer <admin-token>
```

This will:
1. Fetch all verified, approved, and unapplied changes
2. Apply each change to `stocklistdata` table
3. Mark changes as applied
4. Update audit log

**Response:**
```json
{
  "success": true,
  "total_changes": 15,
  "applied_count": 15,
  "error_count": 0,
  "message": "Successfully applied 15 company changes to stocklistdata"
}
```

### Step 4: Monitor Statistics

```bash
GET /api/admin/company-changes/stats
Authorization: Bearer <token>
```

**Response:**
```json
{
  "pending_verification": 5,
  "ready_to_apply": 10,
  "applied": 150,
  "rejected": 3,
  "new_companies": 2,
  "isin_changes": 1,
  "name_changes": 8,
  "code_changes": 4
}
```

## API Endpoints

### Company Changes Management

| Endpoint | Method | Access | Description |
|----------|--------|--------|-------------|
| `/api/admin/company-changes/pending` | GET | Admin/Verifier | Get pending changes |
| `/api/admin/company-changes/{id}` | GET | Admin/Verifier | Get change details |
| `/api/admin/company-changes/{id}/verify` | POST | Admin/Verifier | Verify a change |
| `/api/admin/company-changes/{id}/reject` | POST | Admin/Verifier | Reject a change |
| `/api/admin/company-changes/apply-verified` | POST | Admin Only | Apply all verified changes |
| `/api/admin/company-changes/stats` | GET | Admin/Verifier | Get statistics |

### Query Parameters for `/pending`

- `page`: Page number (default: 1)
- `page_size`: Results per page (default: 50, max: 100)
- `change_type`: Filter by change type
- `is_new_company`: Filter new companies (true/false)

## Examples

### Example 1: New Company Detection

**Detected Change:**
```python
{
    'isin': 'INE999X01015',
    'change_type': 'new',
    'new_name': 'Acme Technologies Ltd',
    'new_bsecode': '543210',
    'new_nsecode': 'ACMETECH',
    'new_securityid': 98765,
    'company_id': None  # NULL for new companies
}
```

**After Verification & Application:**
```sql
-- New row inserted in stocklistdata
INSERT INTO stocklistdata (isin, newname, newbsecode, newnsecode, securityid)
VALUES ('INE999X01015', 'Acme Technologies Ltd', '543210', 'ACMETECH', 98765);
```

### Example 2: Name Change

**Detected Change:**
```python
{
    'isin': 'INE123A01012',
    'change_type': 'name',
    'new_name': 'XYZ Industries Limited',
    'old_name': 'XYZ Industries Ltd',
    'company_id': 'existing-uuid'
}
```

**After Verification & Application:**
```sql
-- Updated in stocklistdata
UPDATE stocklistdata
SET newname = 'XYZ Industries Limited',
    oldname = 'XYZ Industries Ltd'
WHERE isin = 'INE123A01012';
```

### Example 3: Multiple Changes

**Detected Change:**
```python
{
    'isin': 'INE456B01023',
    'change_type': 'bsecode,name,nsecode',  # Comma-separated
    'new_name': 'ABC Corp Ltd',
    'old_name': 'ABC Corporation Limited',
    'new_bsecode': '500100',
    'old_bsecode': '500099',
    'new_nsecode': 'ABCCORP',
    'old_nsecode': 'ABC'
}
```

## Safety Features

1. **No Direct Updates**: Changes never directly modify `stocklistdata`
2. **Audit Trail**: All actions logged in `company_changes_audit_log`
3. **Smart Duplicate Prevention**: Multi-layer duplicate detection system
   - Checks for exact match (same ISIN + same change_type)
   - Checks for any pending change on the same ISIN (different type)
   - Checks for any pending change on the same company_id
   - Prevents submitting changes for companies already in verification queue
4. **Rollback Capable**: Original values preserved in `old_*` columns
5. **Role-Based Access**: Verification by authorized users only
6. **Admin Approval**: Final application requires admin role

## Cronjob Setup

### Recommended Configuration

**See `cronjob_examples.txt` for various crontab configurations.**

**Quick Setup:**
```bash
# 1. Edit crontab
crontab -e

# 2. Add this line for daily detection at 6 AM
0 6 * * * cd /Users/anshulkumar/backfin/src/services/exchange_data/company_management && /usr/bin/python3 detect_changes.py --source-dir ../common >> /var/log/company_changes.log 2>&1

# Or with virtual environment:
0 6 * * * cd /Users/anshulkumar/backfin/src/services/exchange_data/company_management && /Users/anshulkumar/backfin/.venv/bin/python detect_changes.py --source-dir ../common >> /var/log/company_changes.log 2>&1

# 3. Save and exit

# 4. Verify it's scheduled
crontab -l
```

**Important Notes:**
- Use absolute paths in cronjobs
- Specify full Python path (system python3 or virtual environment)
- Redirect output to log file for monitoring
- Script handles errors gracefully with proper exit codes (0=success, 1=error)

### Monitoring

```bash
# View recent runs
tail -f /var/log/company_changes.log

# Check if cronjob is scheduled
crontab -l | grep detect_changes

# Test the exact command your cronjob will run
cd /Users/anshulkumar/backfin/src/services/exchange_data/company_management && /usr/bin/python3 detect_changes.py --source-dir ../common
```

## Troubleshooting

### Issue: Changes not detected

**Solution:**
- Ensure CSV files exist in `../common/` directory
- Check file names: `testtablenew.csv` (current data), `stocklistdata.csv` (new data)
- Verify files have proper ISIN, name, and code columns

### Issue: All changes skipped as duplicates

**Expected Behavior:** The system has smart 3-layer duplicate prevention:
1. Exact match (same ISIN + same change_type)
2. Same ISIN check (any pending change for that ISIN)
3. Same company check (any pending change for that company_id)

**Solution:**
- Check stats: `python3 detect_changes.py --stats-only`
- View pending changes via API: `GET /api/admin/company-changes/pending`
- Process existing changes through verification workflow
- Re-run detection after clearing queue

**Why this matters:**
Prevents duplicate submissions and maintains clean verification workflow.

### Issue: Import errors in cronjob

**Solution:**
- Use full path to Python interpreter
- Ensure virtual environment is activated if using one
- Set `PYTHONPATH` in cronjob if needed:
  ```bash
  0 6 * * * cd /path && export PYTHONPATH=/path/to/parent && python3 detect_changes.py
  ```

### Issue: Permission errors

**Solution:**
```bash
# Make script executable
chmod +x detect_changes.py

# Ensure log directory is writable
sudo mkdir -p /var/log && sudo chown $(whoami) /var/log/company_changes.log
```

### Issue: Verification API not responding

**Solution:**
- Ensure verification system is running: Check `/verification_system/`
- Verify API is on correct port (default: 5002)
- Check `.env` has correct `SUPABASE_URL2` and `SUPABASE_SERVICE_ROLE_KEY`

### Issue: Apply fails

**Possible Causes:**
1. Change not verified: Verify first using `/verify` endpoint
2. Already applied: Check `applied` status
3. Database constraint violation: Review change data for validity

## Best Practices

1. **Regular Detection**: Run change detection weekly or after exchange data updates
2. **Prompt Verification**: Verify changes within 24-48 hours of detection
3. **Batch Application**: Apply verified changes in batches during low-traffic periods
4. **Review Audit Logs**: Regularly check `company_changes_audit_log` for issues
5. **Backup Before Apply**: Take database backup before applying large batches
6. **Test on Staging**: Test the workflow on staging environment first

## Monitoring

### Key Metrics to Track

```sql
-- Pending changes older than 7 days
SELECT COUNT(*) FROM company_changes_pending
WHERE verified = false 
  AND detected_at < NOW() - INTERVAL '7 days';

-- Application success rate
SELECT 
  COUNT(*) FILTER (WHERE applied = true) as applied,
  COUNT(*) FILTER (WHERE verified = true AND applied = false) as pending_apply,
  COUNT(*) FILTER (WHERE review_status = 'rejected') as rejected
FROM company_changes_pending
WHERE detected_at > NOW() - INTERVAL '30 days';

-- Recent audit activity
SELECT action, COUNT(*) as count
FROM company_changes_audit_log
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY action;
```

## Support

For issues or questions:
1. Check audit logs for error details
2. Review change detection output for anomalies
3. Verify database schema is up to date
4. Contact system administrator

---

**Last Updated:** November 2025
**Version:** 1.0.0
