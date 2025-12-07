# Watchlist-Based Announcement Notification System - Architecture Plan

## 📋 Executive Summary

This document outlines an optimized architecture for sending daily digest emails to users containing announcements from companies in their watchlist. The system will replace the current real-time email queueing approach with a batched, end-of-day notification system.

---

## 🎯 Current State Analysis

### Current Implementation Issues:

1. **Real-time Email Queueing**: Currently adds `corp_id` to `emailData` JSON array in real-time as announcements come in
2. **Inefficient Lookup**: Uses JSON array in `UserData.emailData` which is not indexed and hard to query
3. **No Deduplication**: Possible duplicate entries in `emailData` array
4. **No Email Status Tracking**: Can't track if email was sent, failed, or pending
5. **No Historical Data**: Can't analyze what announcements were sent to which users
6. **Scalability Issues**: JSON array grows unbounded, queries become slower over time
7. **No Batch Processing**: No mechanism for daily digest/batch sending

### Current Tables:
- `UserData`: Stores user info including `emailData` JSON array (problematic)
- `watchlistdata`: Maps users to companies (ISIN/category) but uses text userid
- `watchlistnamedata`: Stores watchlist metadata
- `corporatefilings`: Stores all announcements

---

## 🏗️ Proposed Architecture

### **Core Philosophy**: Separation of Concerns + Event-Driven + Batch Processing

### Key Improvements:
1. ✅ **Dedicated notification tracking table** instead of JSON array
2. ✅ **Real-time event capture** but deferred email sending
3. ✅ **Daily batch processing** with digest emails
4. ✅ **Proper indexing** for fast queries
5. ✅ **Email status tracking** (pending, sent, failed)
6. ✅ **Historical audit trail** for analytics
7. ✅ **Graceful degradation** if email service fails

---

## 📊 New Database Schema

### 1. Create `user_notification_queue` Table
Replaces the `emailData` JSON array in `UserData` with a proper relational table.

```sql
-- Drop existing emailData dependency (migration step)
-- Keep emailData column temporarily for backwards compatibility

-- Create user_notification_queue table
CREATE TABLE IF NOT EXISTS public.user_notification_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  corp_id UUID NOT NULL,
  isin TEXT,
  symbol TEXT,
  company_name TEXT,
  category TEXT,
  matched_by TEXT NOT NULL CHECK (matched_by IN ('isin', 'category', 'both')),
  notification_date DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  is_processed BOOLEAN DEFAULT FALSE,
  processed_at TIMESTAMP WITH TIME ZONE,
  
  -- Indexes for performance
  CONSTRAINT user_notification_queue_user_corp_unique UNIQUE (user_id, corp_id, notification_date),
  CONSTRAINT user_notification_queue_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."UserData"("UserID") ON DELETE CASCADE,
  CONSTRAINT user_notification_queue_corp_id_fkey FOREIGN KEY (corp_id) REFERENCES public.corporatefilings(corp_id) ON DELETE CASCADE
);

-- Create indexes for fast queries
CREATE INDEX idx_user_notification_queue_user_id ON user_notification_queue(user_id);
CREATE INDEX idx_user_notification_queue_corp_id ON user_notification_queue(corp_id);
CREATE INDEX idx_user_notification_queue_date ON user_notification_queue(notification_date);
CREATE INDEX idx_user_notification_queue_processed ON user_notification_queue(is_processed) WHERE is_processed = FALSE;
CREATE INDEX idx_user_notification_queue_user_date ON user_notification_queue(user_id, notification_date);

-- Add helpful comments
COMMENT ON TABLE user_notification_queue IS 'Queues announcements for users based on their watchlist - processed daily';
COMMENT ON COLUMN user_notification_queue.matched_by IS 'Whether the announcement matched by ISIN, category, or both';
COMMENT ON COLUMN user_notification_queue.is_processed IS 'Whether this notification has been included in a sent email';
```

### 2. Create `user_email_digest_log` Table
Tracks all digest emails sent to users with their status.

```sql
-- Create email digest log table
CREATE TABLE IF NOT EXISTS public.user_email_digest_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  email_address TEXT NOT NULL,
  digest_date DATE NOT NULL,
  announcement_count INTEGER NOT NULL DEFAULT 0,
  company_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed', 'skipped')),
  error_message TEXT,
  email_provider_id TEXT, -- Resend API message ID
  corp_ids UUID[], -- Array of announcement IDs included in this digest
  sent_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  CONSTRAINT user_email_digest_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."UserData"("UserID") ON DELETE CASCADE,
  CONSTRAINT user_email_digest_unique UNIQUE (user_id, digest_date)
);

-- Create indexes
CREATE INDEX idx_user_email_digest_log_user_id ON user_email_digest_log(user_id);
CREATE INDEX idx_user_email_digest_log_date ON user_email_digest_log(digest_date);
CREATE INDEX idx_user_email_digest_log_status ON user_email_digest_log(status);
CREATE INDEX idx_user_email_digest_log_sent_at ON user_email_digest_log(sent_at);

-- Add helpful comments
COMMENT ON TABLE user_email_digest_log IS 'Tracks daily digest emails sent to users with delivery status';
COMMENT ON COLUMN user_email_digest_log.corp_ids IS 'Array of corp_ids included in this digest email';
```

### 3. Create `user_notification_preferences` Table
Allows users to configure notification settings.

```sql
-- Create notification preferences table
CREATE TABLE IF NOT EXISTS public.user_notification_preferences (
  user_id UUID PRIMARY KEY,
  email_enabled BOOLEAN DEFAULT TRUE,
  digest_time TIME DEFAULT '18:00:00', -- Default 6 PM
  digest_timezone TEXT DEFAULT 'Asia/Kolkata',
  minimum_announcements INTEGER DEFAULT 1, -- Minimum announcements to send email
  include_categories TEXT[], -- NULL means all categories
  exclude_categories TEXT[], -- Categories to exclude
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  CONSTRAINT user_notification_preferences_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."UserData"("UserID") ON DELETE CASCADE
);

-- Create index
CREATE INDEX idx_user_notification_preferences_email_enabled ON user_notification_preferences(email_enabled);

COMMENT ON TABLE user_notification_preferences IS 'User preferences for notification delivery';
```

### 4. Fix `watchlistdata` Schema
Current issue: `userid` is TEXT but should be UUID for proper referencing.

```sql
-- Migration to fix watchlistdata.userid type
-- Step 1: Add new column
ALTER TABLE public.watchlistdata ADD COLUMN user_id_uuid UUID;

-- Step 2: Migrate data (cast text to uuid where valid)
UPDATE public.watchlistdata 
SET user_id_uuid = userid::uuid 
WHERE userid IS NOT NULL AND userid ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

-- Step 3: Add foreign key constraint
ALTER TABLE public.watchlistdata 
ADD CONSTRAINT watchlistdata_user_id_fkey 
FOREIGN KEY (user_id_uuid) REFERENCES public."UserData"("UserID") ON DELETE CASCADE;

-- Step 4: Create indexes
CREATE INDEX idx_watchlistdata_user_id_uuid ON watchlistdata(user_id_uuid);
CREATE INDEX idx_watchlistdata_isin ON watchlistdata(isin);
CREATE INDEX idx_watchlistdata_category ON watchlistdata(category);

-- Note: Keep old 'userid' column for backwards compatibility during transition
-- Drop it later: ALTER TABLE watchlistdata DROP COLUMN userid;
```

---

## 🔄 System Workflow

### **Phase 1: Real-time Queue Population** (When announcement arrives)

```
New Announcement → insert_new_announcement() API
    ↓
1. Broadcast via WebSocket (current behavior - KEEP)
    ↓
2. Find matching users:
   - Query watchlistdata for users watching this ISIN
   - Query watchlistdata for users watching this category
   - Deduplicate user list
    ↓
3. Insert into user_notification_queue:
   - One row per (user_id, corp_id) pair
   - UNIQUE constraint prevents duplicates
   - Store matched_by reason for analytics
    ↓
4. Return success (DO NOT send email immediately)
```

**Key Change**: Replace `emailData` JSON array update with relational table insert.

---

### **Phase 2: Daily Batch Processing** (End of day - Cron job)

```
Daily Cron Job (e.g., 6 PM IST)
    ↓
1. Fetch unprocessed notifications grouped by user:
   SELECT user_id, array_agg(corp_id) as corp_ids
   FROM user_notification_queue
   WHERE is_processed = FALSE 
     AND notification_date = CURRENT_DATE
   GROUP BY user_id
    ↓
2. For each user:
   a. Check notification preferences (email_enabled, minimum_announcements)
   b. Fetch full announcement details from corporatefilings
   c. Group announcements by company
   d. Generate HTML digest email using notification_service.py
   e. Send via Resend API
    ↓
3. Update status:
   a. Mark notifications as processed (is_processed = TRUE)
   b. Log to user_email_digest_log (status = 'sent' or 'failed')
   c. Store Resend message ID for tracking
    ↓
4. Handle failures:
   - Retry failed emails (exponential backoff)
   - Log errors to user_email_digest_log
   - Alert admin if too many failures
```

---

## 💻 Implementation Plan

### **Step 1: Database Migration** (Day 1)

Create migration script: `/scripts/migrations/add_notification_tables.sql`

```sql
-- Run all CREATE TABLE statements from above
-- Run ALTER TABLE for watchlistdata fix
-- Add triggers if needed (optional)
```

Execute:
```bash
# Test in Supabase SQL editor first
# Then commit to repo
```

---

### **Step 2: Update API Endpoint** (Day 1-2)

Update `api/app.py` → `insert_new_announcement()` function:

```python
@app.route('/api/insert_new_announcement', methods=['POST', 'OPTIONS'])
def insert_new_announcement():
    # ... existing validation code ...
    
    # Broadcast WebSocket (KEEP THIS)
    socketio.emit('new_announcement', new_announcement, room='all')
    
    # NEW: Queue notifications instead of updating emailData
    isin = data.get('isin')
    category = data.get('category')
    corp_id = data.get('corp_id')
    symbol = data.get('symbol')
    company_name = data.get('companyname')
    
    # Get matching users
    user_ids = get_all_users(isin, category)
    
    # Insert into notification queue (batch insert for efficiency)
    notification_records = []
    for user_id in user_ids:
        # Determine match reason
        is_isin_match = user_id in get_users_by_isin(isin)
        is_category_match = user_id in get_user_by_category(category)
        
        if is_isin_match and is_category_match:
            matched_by = 'both'
        elif is_isin_match:
            matched_by = 'isin'
        else:
            matched_by = 'category'
        
        notification_records.append({
            'user_id': user_id,
            'corp_id': corp_id,
            'isin': isin,
            'symbol': symbol,
            'company_name': company_name,
            'category': category,
            'matched_by': matched_by,
            'notification_date': dt.date.today().isoformat()
        })
    
    # Batch insert (handles duplicates via UNIQUE constraint)
    if notification_records:
        try:
            supabase.table('user_notification_queue').insert(
                notification_records,
                on_conflict='user_id,corp_id,notification_date'  # Upsert behavior
            ).execute()
            logger.info(f"Queued {len(notification_records)} notifications for {len(user_ids)} users")
        except Exception as e:
            logger.error(f"Failed to queue notifications: {e}")
            # Don't fail the entire request if notification queueing fails
    
    # REMOVE: Old emailData JSON array update code
    # DELETE THIS BLOCK:
    # for user_id in user_ids:
    #     response = supabase.table('UserData').select('emailData')...
    
    return jsonify({'message': 'Announcement broadcast and queued successfully', 'status': 'success'}), 200
```

---

### **Step 3: Create Daily Digest Sender** (Day 2-3)

Create new file: `/scripts/send_daily_digest.py`

```python
#!/usr/bin/env python3
"""
Daily Digest Email Sender
Sends watchlist-based announcement digests to users
Run via cron: 0 18 * * * python3 /path/to/send_daily_digest.py
"""

import os
import sys
from datetime import datetime, date
from typing import List, Dict
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.notification_service import AnnouncementMailer
from supabase import create_client, Client
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'/var/log/backfin/digest_{date.today().isoformat()}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('daily_digest')

# Load environment
load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL2')
SUPABASE_KEY = os.getenv('SUPABASE_KEY2')
RESEND_API_KEY = os.getenv('RESEND_API')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
mailer = AnnouncementMailer(api_key=RESEND_API_KEY)


def get_users_with_pending_notifications(target_date: date) -> List[str]:
    """Get list of users with pending notifications for the given date"""
    try:
        response = supabase.table('user_notification_queue')\
            .select('user_id')\
            .eq('notification_date', target_date.isoformat())\
            .eq('is_processed', False)\
            .execute()
        
        # Deduplicate user IDs
        user_ids = list(set([row['user_id'] for row in response.data]))
        logger.info(f"Found {len(user_ids)} users with pending notifications")
        return user_ids
    except Exception as e:
        logger.error(f"Failed to fetch users: {e}")
        return []


def get_user_notifications(user_id: str, target_date: date) -> List[Dict]:
    """Get all pending notifications for a user on the given date"""
    try:
        response = supabase.table('user_notification_queue')\
            .select('*')\
            .eq('user_id', user_id)\
            .eq('notification_date', target_date.isoformat())\
            .eq('is_processed', False)\
            .execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Failed to fetch notifications for user {user_id}: {e}")
        return []


def get_announcement_details(corp_ids: List[str]) -> List[Dict]:
    """Fetch full announcement details from corporatefilings"""
    try:
        response = supabase.table('corporatefilings')\
            .select('*')\
            .in_('corp_id', corp_ids)\
            .execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Failed to fetch announcement details: {e}")
        return []


def get_user_email(user_id: str) -> str:
    """Get user's email address"""
    try:
        response = supabase.table('UserData')\
            .select('emailID')\
            .eq('UserID', user_id)\
            .single()\
            .execute()
        
        return response.data.get('emailID') if response.data else None
    except Exception as e:
        logger.error(f"Failed to fetch email for user {user_id}: {e}")
        return None


def check_user_preferences(user_id: str, announcement_count: int) -> bool:
    """Check if user wants to receive email based on preferences"""
    try:
        response = supabase.table('user_notification_preferences')\
            .select('*')\
            .eq('user_id', user_id)\
            .single()\
            .execute()
        
        if response.data:
            prefs = response.data
            
            # Check if email is enabled
            if not prefs.get('email_enabled', True):
                return False
            
            # Check minimum announcement threshold
            min_announcements = prefs.get('minimum_announcements', 1)
            if announcement_count < min_announcements:
                logger.info(f"User {user_id}: {announcement_count} announcements < minimum {min_announcements}")
                return False
            
            return True
        else:
            # No preferences = default behavior (send email)
            return True
    except Exception as e:
        logger.warning(f"Failed to fetch preferences for user {user_id}, defaulting to send: {e}")
        return True  # Default to sending if preference check fails


def group_announcements_by_company(announcements: List[Dict]) -> Dict[str, List[Dict]]:
    """Group announcements by company"""
    grouped = {}
    
    for announcement in announcements:
        company_key = announcement.get('symbol') or announcement.get('isin') or announcement.get('companyname')
        
        if company_key not in grouped:
            grouped[company_key] = {
                'companyname': announcement.get('companyname', 'Unknown Company'),
                'symbol': announcement.get('symbol', ''),
                'isin': announcement.get('isin', ''),
                'announcements': []
            }
        
        grouped[company_key]['announcements'].append({
            'summary': announcement.get('summary', ''),
            'ai_summary': announcement.get('ai_summary', ''),
            'category': announcement.get('category', ''),
            'date': announcement.get('date', ''),
            'url': announcement.get('fileurl', '#'),
            'ai_url': f"https://yourapp.com/announcement/{announcement.get('corp_id')}"  # Update with actual URL
        })
    
    return grouped


def send_digest_to_user(user_id: str, target_date: date) -> bool:
    """Send daily digest email to a single user"""
    try:
        # Get user's email
        email = get_user_email(user_id)
        if not email:
            logger.warning(f"No email found for user {user_id}")
            return False
        
        # Get pending notifications
        notifications = get_user_notifications(user_id, target_date)
        if not notifications:
            logger.info(f"No notifications for user {user_id}")
            return False
        
        # Check user preferences
        if not check_user_preferences(user_id, len(notifications)):
            logger.info(f"User {user_id} preferences: skipping email")
            mark_notifications_processed(user_id, target_date, 'skipped')
            return True  # Not a failure
        
        # Get announcement details
        corp_ids = [n['corp_id'] for n in notifications]
        announcements = get_announcement_details(corp_ids)
        
        if not announcements:
            logger.warning(f"No announcement details found for user {user_id}")
            return False
        
        # Group by company
        grouped = group_announcements_by_company(announcements)
        
        # Send email for each company (or combine into one digest)
        company_count = len(grouped)
        announcement_count = len(announcements)
        
        logger.info(f"Sending digest to {email}: {announcement_count} announcements from {company_count} companies")
        
        # Use existing notification_service to send email
        # Option 1: One email per company
        for company_key, company_data in grouped.items():
            html_content = mailer.generate_email_template(company_data)
            
            # Send via Resend
            result = mailer.send_email(
                to_email=email,
                subject=f"📊 Daily Digest: {company_data['companyname']} ({len(company_data['announcements'])} announcements)",
                html_content=html_content
            )
            
            if not result:
                logger.error(f"Failed to send email to {email} for {company_key}")
                return False
        
        # Mark notifications as processed
        mark_notifications_processed(user_id, target_date, 'sent', corp_ids)
        
        # Log to digest log
        log_digest_sent(user_id, email, target_date, announcement_count, company_count, corp_ids, 'sent')
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending digest to user {user_id}: {e}")
        log_digest_sent(user_id, email, target_date, 0, 0, [], 'failed', str(e))
        return False


def mark_notifications_processed(user_id: str, target_date: date, status: str, corp_ids: List[str] = None):
    """Mark notifications as processed"""
    try:
        update_query = supabase.table('user_notification_queue')\
            .update({
                'is_processed': True,
                'processed_at': datetime.now().isoformat()
            })\
            .eq('user_id', user_id)\
            .eq('notification_date', target_date.isoformat())
        
        if corp_ids:
            update_query = update_query.in_('corp_id', corp_ids)
        
        update_query.execute()
        logger.info(f"Marked notifications processed for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to mark notifications processed: {e}")


def log_digest_sent(user_id: str, email: str, digest_date: date, 
                    announcement_count: int, company_count: int, 
                    corp_ids: List[str], status: str, error_msg: str = None):
    """Log digest email to audit table"""
    try:
        supabase.table('user_email_digest_log').insert({
            'user_id': user_id,
            'email_address': email,
            'digest_date': digest_date.isoformat(),
            'announcement_count': announcement_count,
            'company_count': company_count,
            'status': status,
            'error_message': error_msg,
            'corp_ids': corp_ids,
            'sent_at': datetime.now().isoformat() if status == 'sent' else None
        }).execute()
    except Exception as e:
        logger.error(f"Failed to log digest: {e}")


def main():
    """Main execution function"""
    target_date = date.today()
    logger.info(f"Starting daily digest processing for {target_date}")
    
    # Get all users with pending notifications
    user_ids = get_users_with_pending_notifications(target_date)
    
    if not user_ids:
        logger.info("No users with pending notifications")
        return 0
    
    # Process each user
    success_count = 0
    failure_count = 0
    
    for user_id in user_ids:
        try:
            if send_digest_to_user(user_id, target_date):
                success_count += 1
            else:
                failure_count += 1
        except Exception as e:
            logger.error(f"Unhandled error for user {user_id}: {e}")
            failure_count += 1
    
    logger.info(f"Digest processing complete: {success_count} success, {failure_count} failures")
    
    return 0 if failure_count == 0 else 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
```

---

### **Step 4: Update notification_service.py** (Day 3)

Add method to `AnnouncementMailer` class:

```python
def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
    """Send email via Resend API"""
    try:
        params = {
            "from": "Backfin <notifications@backfin.com>",  # Update with your domain
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
        
        email = resend.Emails.send(params)
        logger.info(f"Email sent successfully to {to_email}: {email['id']}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False
```

---

### **Step 5: Setup Cron Job** (Day 3)

Add to server crontab:

```bash
# Edit crontab
crontab -e

# Add daily digest job (runs at 6 PM IST every day)
0 18 * * * cd /Users/anshulkumar/backfin && /usr/bin/python3 scripts/send_daily_digest.py >> /var/log/backfin/digest_cron.log 2>&1

# Alternative: Run at multiple times for different timezones
0 18 * * * cd /Users/anshulkumar/backfin && /usr/bin/python3 scripts/send_daily_digest.py --timezone=Asia/Kolkata
0 9 * * * cd /Users/anshulkumar/backfin && /usr/bin/python3 scripts/send_daily_digest.py --timezone=America/New_York
```

---

## 📈 Benefits of New Architecture

### 1. **Performance**
- ✅ Indexed queries (10-100x faster than JSON array scanning)
- ✅ Batch processing instead of per-announcement updates
- ✅ Reduced database writes (1 insert vs N updates)

### 2. **Scalability**
- ✅ Handles millions of notifications efficiently
- ✅ No bounded array growth issues
- ✅ Horizontal scaling possible (partition by date)

### 3. **Reliability**
- ✅ ACID transactions prevent data loss
- ✅ Retry mechanism for failed emails
- ✅ Audit trail for debugging

### 4. **User Experience**
- ✅ Daily digest instead of spam
- ✅ Grouped by company for easy reading
- ✅ Configurable preferences
- ✅ Better email formatting

### 5. **Analytics**
- ✅ Track email open rates (via Resend)
- ✅ Measure notification effectiveness
- ✅ Identify popular categories/companies

### 6. **Maintainability**
- ✅ Clean separation of concerns
- ✅ Easy to add new notification channels (SMS, Push)
- ✅ Testable components

---

## 🔄 Migration Strategy

### Phase 1: Add New Tables (Non-breaking)
- Create all new tables
- Keep `emailData` column in `UserData`
- Run both systems in parallel

### Phase 2: Gradual Rollout
- Update API to write to both `emailData` AND `user_notification_queue`
- Deploy digest sender but mark as TEST mode
- Monitor for 1 week

### Phase 3: Cutover
- Disable `emailData` writes
- Enable production digest sender
- Monitor email delivery rates

### Phase 4: Cleanup
- Drop `emailData` column from `UserData` (after 30 days)
- Archive old notification records (keep last 90 days)

---

## 🚨 Monitoring & Alerts

### Key Metrics:
1. **Notification Queue Depth**: Alert if > 10,000 unprocessed
2. **Email Failure Rate**: Alert if > 5%
3. **Digest Processing Time**: Alert if > 30 minutes
4. **User Complaints**: Track "didn't receive email" tickets

### Dashboards:
- Daily email sent count (trend)
- Top companies by notification count
- User engagement rate (click-through)
- Error distribution by type

---

## 🔐 Security Considerations

1. **Email Rate Limiting**: Max 100 emails/minute to prevent abuse
2. **Unsubscribe Link**: Add to every email
3. **Data Privacy**: Only send to verified email addresses
4. **API Key Rotation**: Rotate Resend API key quarterly
5. **SQL Injection**: Use parameterized queries (already done)

---

## 💰 Cost Analysis

### Current Approach:
- Database writes: 1,000 announcements/day × 100 users = 100,000 writes
- Email sends: Real-time (high frequency, potential spam)

### New Approach:
- Database writes: 1,000 announcements/day × 100 users = 100,000 inserts (same)
- Email sends: 100 users × 1 digest/day = 100 emails (99% reduction)
- Resend cost: 100 emails × $0.001 = $0.10/day = $3/month

**Savings**: ~99% reduction in email volume + better user experience

---

## 🎯 Success Metrics

After 30 days, measure:
- [ ] Email delivery rate > 95%
- [ ] User complaints < 1%
- [ ] Avg email open rate > 20%
- [ ] Avg click-through rate > 10%
- [ ] Database query time < 100ms (p95)
- [ ] Digest processing time < 10 minutes

---

## 📚 Next Steps (Priority Order)

1. ✅ **Review this architecture** with team
2. ⏳ **Create database migrations** (1 day)
3. ⏳ **Update API endpoint** (1 day)
4. ⏳ **Build digest sender script** (2 days)
5. ⏳ **Add email template** (1 day)
6. ⏳ **Setup cron job** (0.5 day)
7. ⏳ **Test end-to-end** (1 day)
8. ⏳ **Deploy to staging** (0.5 day)
9. ⏳ **Monitor for 1 week** (ongoing)
10. ⏳ **Deploy to production** (0.5 day)

**Total estimated time**: 7-8 days

---

## 📞 Support

For questions or issues:
- Architecture questions: [your-email]
- Implementation help: Check `/docs/notification-system.md`
- Bug reports: GitHub Issues

---

**Document Version**: 1.0  
**Last Updated**: 28 November 2025  
**Author**: AI Architecture Assistant  
**Status**: 🟡 Pending Review
