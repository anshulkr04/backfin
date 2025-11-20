# Role-Based Review System Documentation

## Overview

The verification system now includes a comprehensive role-based access control (RBAC) system with two distinct roles and a review queue for quality control.

## Roles

### 1. Verifier (Default Role)
- Can view and verify unverified announcements
- Can update announcement details
- Can mark announcements as verified
- Can unverify announcements (send back to queue)
- **Cannot** access the review queue
- **Cannot** send announcements to review

### 2. Admin (Elevated Role)
- All verifier permissions, plus:
- Can access the review queue
- Can send verified announcements to review
- Can approve or reject announcements in review
- Can see review statistics
- Full system access

## Database Schema Changes

### New Columns in `admin_users` Table
```sql
role TEXT DEFAULT 'verifier' CHECK (role IN ('admin', 'verifier'))
```

### New Columns in `corporatefilings` Table
```sql
review_status TEXT CHECK (review_status IN (NULL, 'pending_review', 'approved', 'rejected'))
sent_to_review_at TIMESTAMPTZ
sent_to_review_by UUID REFERENCES admin_users(id)
review_notes TEXT
reviewed_at TIMESTAMPTZ
reviewed_by UUID REFERENCES admin_users(id)
```

### New Table: `verification_audit_log`
Tracks all verification and review actions for audit purposes.

## Review Workflow

```
1. Verifier marks announcement as verified
   ↓
2. Admin reviews verified announcements
   ↓
3. Admin can:
   a) Approve → Keeps verified status, marks as 'approved'
   b) Send to Review → Flags for review with notes
   c) Reject → Sends back to verification queue (unverified)
```

## API Endpoints

### Role Management

#### Check User Role
```bash
GET /api/admin/auth/me
Authorization: Bearer <token>
```

Response includes user role:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "User Name",
  "role": "admin"
}
```

### Review Queue Endpoints (Admin Only)

#### 1. Send Verified Announcement to Review
```bash
POST /api/admin/announcements/{corp_id}/send-to-review
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "notes": "Please review the financial numbers in this announcement"
}
```

**Response:**
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

#### 2. Get Review Queue
```bash
GET /api/admin/review-queue?page=1&page_size=50
Authorization: Bearer <admin-token>
```

**Query Parameters:**
- `page` (integer): Page number, starts at 1 (default: 1)
- `page_size` (integer): Results per page, max 100 (default: 50)
- `start_date` (string): Filter from date YYYY-MM-DD (optional)
- `end_date` (string): Filter to date YYYY-MM-DD (optional)
- `category` (string): Filter by category (optional)

**Response:**
```json
{
  "announcements": [
    {
      "corp_id": "uuid",
      "headline": "Q3 Financial Results",
      "category": "Financial Results",
      "verified": true,
      "verified_at": "2025-11-21T09:00:00",
      "verified_by": "verifier-uuid",
      "review_status": "pending_review",
      "sent_to_review_at": "2025-11-21T10:30:00",
      "sent_to_review_by": "admin-uuid",
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

#### 3. Review Announcement (Approve/Reject)
```bash
POST /api/admin/announcements/{corp_id}/review
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "action": "approve",
  "notes": "Numbers verified from company website"
}
```

**Actions:**
- `"approve"` - Keeps verified status, marks as approved
- `"reject"` - Sends back to verification queue (unverified)

**Response (Approve):**
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

**Response (Reject):**
```json
{
  "success": true,
  "corp_id": "uuid",
  "action": "reject",
  "review_status": "rejected",
  "reviewed_at": "2025-11-21T11:00:00",
  "reviewed_by": "admin-uuid",
  "message": "Announcement rejected and sent back to verification queue"
}
```

### Updated Statistics Endpoint
```bash
GET /api/admin/stats
Authorization: Bearer <token>
```

**Verifier Response:**
```json
{
  "unverified": 450,
  "verified_total": 1200,
  "verified_today": 35,
  "user_role": "verifier"
}
```

**Admin Response (includes review stats):**
```json
{
  "unverified": 450,
  "verified_total": 1200,
  "verified_today": 35,
  "user_role": "admin",
  "review_queue": {
    "pending_review": 15,
    "approved": 890,
    "rejected": 23
  }
}
```

## Setup Instructions

### 1. Run SQL Migration

Execute the SQL script to add role-based features:

```bash
# In Supabase SQL Editor
psql -f verification_system/ROLE_BASED_REVIEW_SYSTEM.sql
```

Or run directly in Supabase SQL Editor:
```sql
-- See ROLE_BASED_REVIEW_SYSTEM.sql for full script
```

### 2. Update Existing Users to Admin

To promote existing users to admin role:

```sql
UPDATE admin_users 
SET role = 'admin' 
WHERE email = 'your-admin@example.com';
```

Or promote all existing users:

```sql
UPDATE admin_users 
SET role = 'admin' 
WHERE role = 'verifier';
```

### 3. Restart the Service

```bash
cd verification_system
docker-compose down
docker-compose up -d --build
```

### 4. Verify Role System

```bash
# Login and check role
TOKEN=$(curl -X POST http://localhost:5002/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "YourPassword"
  }' | jq -r '.access_token')

# Check current user role
curl http://localhost:5002/api/admin/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq .
```

## Use Cases

### Use Case 1: Quality Control Review
1. Verifier marks 100 announcements as verified
2. Admin reviews a sample (e.g., 10%)
3. Admin sends suspicious ones to review queue
4. Admin either approves or rejects after review

### Use Case 2: Training New Verifiers
1. New verifier marks announcements as verified
2. Admin reviews all their work initially
3. Gradually reduce review percentage as quality improves
4. Track accuracy via audit log

### Use Case 3: Disputed Verifications
1. Verifier marks announcement as verified
2. Another team member notices an issue
3. Admin sends to review queue with notes
4. Admin makes final decision (approve/reject)

## Error Handling

### 403 Forbidden - Insufficient Permissions
```json
{
  "detail": "Admin access required. You do not have permission to access this resource."
}
```

**Solution:** User must be promoted to admin role.

### 400 Bad Request - Invalid Action
```json
{
  "detail": "Only verified announcements can be sent to review"
}
```

**Solution:** Announcement must be verified first.

## Security Considerations

1. **Role Assignment:** Only database admins can change user roles
2. **Audit Trail:** All actions are logged in `verification_audit_log`
3. **Token Validation:** Role is embedded in JWT token
4. **Session Management:** Role changes require re-login

## Monitoring & Analytics

### Check Audit Log
```sql
SELECT 
  val.created_at,
  au.email as user_email,
  au.role as user_role,
  val.action,
  cf.headline,
  cf.category,
  val.notes
FROM verification_audit_log val
JOIN admin_users au ON val.user_id = au.id
JOIN corporatefilings cf ON val.corp_id = cf.corp_id
ORDER BY val.created_at DESC
LIMIT 50;
```

### Review Queue Performance
```sql
SELECT 
  DATE(sent_to_review_at) as review_date,
  COUNT(*) as sent_to_review,
  COUNT(CASE WHEN review_status = 'approved' THEN 1 END) as approved,
  COUNT(CASE WHEN review_status = 'rejected' THEN 1 END) as rejected,
  COUNT(CASE WHEN review_status = 'pending_review' THEN 1 END) as pending
FROM corporatefilings
WHERE sent_to_review_at IS NOT NULL
GROUP BY DATE(sent_to_review_at)
ORDER BY review_date DESC;
```

## Best Practices

1. **Regular Reviews:** Admins should review queue daily
2. **Clear Notes:** Always provide context when sending to review
3. **Timely Decisions:** Don't let review queue accumulate
4. **Role Assignment:** Promote users to admin carefully
5. **Audit Monitoring:** Regularly check audit logs
6. **Training:** Use rejected items to train verifiers

## Migration Checklist

- [ ] Run SQL migration script
- [ ] Update existing users to admin role (if needed)
- [ ] Restart Docker containers
- [ ] Test admin login and role verification
- [ ] Test review queue endpoints
- [ ] Test approve/reject functionality
- [ ] Verify audit logging is working
- [ ] Update frontend to show/hide review features based on role
- [ ] Train team on new workflow
- [ ] Document any custom policies or procedures
