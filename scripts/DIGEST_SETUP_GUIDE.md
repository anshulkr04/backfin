# Daily Digest Email System - Setup & Testing Guide

## 🎯 Overview

This system sends daily digest emails to users containing announcements from companies in their watchlist. It replaces the old JSON array approach with a proper relational database architecture.

## ✅ What's Been Implemented

### 1. Database Schema (Already Done)
- ✅ `user_notification_queue` - Stores pending notifications
- ✅ `user_email_digest_log` - Tracks sent emails
- ✅ `user_notification_preferences` - User settings (optional)

### 2. API Updates (Already Done)
- ✅ Updated `api/app.py` → `insert_new_announcement()` endpoint
- ✅ Queues notifications instead of updating JSON array
- ✅ Batch insert for efficiency
- ✅ Graceful error handling

### 3. Scripts Created (Already Done)
- ✅ `scripts/send_daily_digest.py` - Daily digest sender
- ✅ `scripts/test_digest_system.py` - Test suite

---

## 🚀 Quick Start

### Step 1: Test the System

```bash
# Navigate to project directory
cd /Users/anshulkumar/backfin

# Activate virtual environment
source .venv/bin/activate

# Run test suite
python3 scripts/test_digest_system.py
```

This will verify:
- ✓ Can queue notifications
- ✓ Can fetch pending notifications
- ✓ Database tables exist
- ✓ Watchlist data is accessible

### Step 2: Dry Run (No Emails Sent)

```bash
# Test digest generation without sending emails
python3 scripts/send_daily_digest.py --dry-run
```

Expected output:
```
📊 Found X users with pending notifications
🧪 DRY RUN: Would send email to user@example.com
   Subject: 📊 Daily Watchlist Digest: 5 new announcements
   Companies: Company A, Company B, Company C
✅ Successful: X
```

### Step 3: Send Test Email to Yourself

First, find your user ID:
```bash
# In Supabase SQL editor or via API
SELECT "UserID", "emailID" FROM "UserData" WHERE "emailID" = 'your@email.com';
```

Then send test email:
```bash
python3 scripts/send_daily_digest.py --test-user YOUR_USER_ID
```

### Step 4: Run for Real (All Users)

```bash
# Send digests to all users with pending notifications
python3 scripts/send_daily_digest.py
```

---

## ⚙️ Cron Job Setup

### Option 1: Daily at 6 PM IST

```bash
# Edit crontab
crontab -e

# Add this line (adjust path as needed)
0 18 * * * cd /Users/anshulkumar/backfin && /usr/bin/python3 scripts/send_daily_digest.py >> /var/log/backfin/digest.log 2>&1
```

### Option 2: Multiple Times Per Day

```bash
# Morning digest at 9 AM
0 9 * * * cd /Users/anshulkumar/backfin && /usr/bin/python3 scripts/send_daily_digest.py >> /var/log/backfin/digest_morning.log 2>&1

# Evening digest at 6 PM
0 18 * * * cd /Users/anshulkumar/backfin && /usr/bin/python3 scripts/send_daily_digest.py >> /var/log/backfin/digest_evening.log 2>&1
```

### Option 3: Using systemd Timer (Linux)

Create `/etc/systemd/system/backfin-digest.service`:
```ini
[Unit]
Description=Backfin Daily Digest Email Sender
After=network.target

[Service]
Type=oneshot
User=your-user
WorkingDirectory=/Users/anshulkumar/backfin
ExecStart=/usr/bin/python3 scripts/send_daily_digest.py
StandardOutput=append:/var/log/backfin/digest.log
StandardError=append:/var/log/backfin/digest.log

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/backfin-digest.timer`:
```ini
[Unit]
Description=Run Backfin Daily Digest at 6 PM
Requires=backfin-digest.service

[Timer]
OnCalendar=18:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable backfin-digest.timer
sudo systemctl start backfin-digest.timer
sudo systemctl status backfin-digest.timer
```

---

## 📧 Email Configuration

### Resend API Setup

1. **Get API Key**: https://resend.com/api-keys
2. **Verify Domain**: Add your sending domain (e.g., backfin.com)
3. **Add to .env**:
```bash
RESEND_API=re_xxxxxxxxxxxxx
```

### Update Email Sender

In `scripts/send_daily_digest.py`, update line ~380:
```python
"from": "Backfin Notifications <notifications@backfin.com>",  # Your verified domain
```

### Email Template Customization

In `scripts/send_daily_digest.py`, update `generate_combined_digest_html()` function to customize:
- Colors and styling
- Company logo/branding
- Unsubscribe link
- Footer links

---

## 🔧 Script Options

### send_daily_digest.py Options

```bash
# Send for specific date
python3 scripts/send_daily_digest.py --date 2025-11-28

# Test with single user
python3 scripts/send_daily_digest.py --test-user USER_ID

# Dry run (no emails sent)
python3 scripts/send_daily_digest.py --dry-run

# Combine options
python3 scripts/send_daily_digest.py --date 2025-11-28 --dry-run
```

---

## 📊 Monitoring & Logs

### Check Logs

```bash
# View today's log
tail -f /var/log/backfin/digest_$(date +%Y-%m-%d).log

# View all logs
ls -lah /var/log/backfin/

# Search for errors
grep "❌" /var/log/backfin/digest_*.log

# Count successes
grep "✅ Email sent" /var/log/backfin/digest_*.log | wc -l
```

### Database Queries

```sql
-- Check pending notifications
SELECT 
    notification_date,
    COUNT(DISTINCT user_id) as users,
    COUNT(*) as total_notifications
FROM user_notification_queue
WHERE is_processed = FALSE
GROUP BY notification_date
ORDER BY notification_date DESC;

-- Check email send status
SELECT 
    status,
    COUNT(*) as count,
    SUM(announcement_count) as total_announcements
FROM user_email_digest_log
WHERE digest_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY status;

-- Recent digest emails
SELECT 
    email_address,
    digest_date,
    announcement_count,
    company_count,
    status,
    sent_at
FROM user_email_digest_log
ORDER BY created_at DESC
LIMIT 10;

-- Users with most notifications
SELECT 
    u."emailID",
    COUNT(*) as notification_count
FROM user_notification_queue nq
JOIN "UserData" u ON nq.user_id = u."UserID"
WHERE nq.notification_date = CURRENT_DATE
  AND nq.is_processed = FALSE
GROUP BY u."emailID"
ORDER BY notification_count DESC
LIMIT 10;
```

---

## 🛠️ Troubleshooting

### Issue: No emails being sent

**Check 1: Are there pending notifications?**
```sql
SELECT COUNT(*) FROM user_notification_queue 
WHERE notification_date = CURRENT_DATE 
AND is_processed = FALSE;
```

**Check 2: Are users' emails valid?**
```sql
SELECT "UserID", "emailID" FROM "UserData" 
WHERE "emailID" IS NULL OR "emailID" = '';
```

**Check 3: Is Resend API key valid?**
```bash
python3 -c "
import resend
import os
from dotenv import load_dotenv
load_dotenv()
resend.api_key = os.getenv('RESEND_API')
print('API key:', resend.api_key[:10] + '...')
"
```

### Issue: Emails marked as spam

**Solutions:**
1. Verify your domain with Resend (SPF, DKIM, DMARC)
2. Add unsubscribe link
3. Use recognizable sender name
4. Avoid spam trigger words
5. Send from consistent domain

### Issue: Script crashes

**Check Python version:**
```bash
python3 --version  # Should be 3.8+
```

**Check dependencies:**
```bash
pip install resend supabase python-dotenv
```

**Check permissions:**
```bash
chmod +x scripts/send_daily_digest.py
ls -la scripts/send_daily_digest.py
```

### Issue: Old emailData still being used

The old system writes to `UserData.emailData` JSON array. After confirming the new system works:

1. **Stop writing to emailData** (already done in API update)
2. **Clear old data** (optional):
```sql
UPDATE "UserData" SET "emailData" = NULL;
```

---

## 📈 Performance Tips

### 1. Database Indexing
Already created in schema, but verify:
```sql
-- Check indexes
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'user_notification_queue';
```

### 2. Batch Processing
The script processes users sequentially. For large user bases:
- Add rate limiting: `time.sleep(0.1)` between emails
- Implement parallel processing with multiprocessing
- Use Resend's batch API (if available)

### 3. Clean Up Old Data
Archive old notifications monthly:
```sql
-- Delete processed notifications older than 90 days
DELETE FROM user_notification_queue
WHERE is_processed = TRUE
AND created_at < NOW() - INTERVAL '90 days';

-- Archive old logs (move to archive table)
INSERT INTO user_email_digest_log_archive
SELECT * FROM user_email_digest_log
WHERE created_at < NOW() - INTERVAL '1 year';

DELETE FROM user_email_digest_log
WHERE created_at < NOW() - INTERVAL '1 year';
```

---

## 🔐 Security Checklist

- [ ] Resend API key stored in `.env` (not in code)
- [ ] `.env` file in `.gitignore`
- [ ] Email rate limiting implemented
- [ ] Unsubscribe link added to emails
- [ ] User preferences respected
- [ ] SQL injection prevention (using parameterized queries)
- [ ] Log files have appropriate permissions (600 or 640)

---

## 📝 User Preferences (Optional)

Users can customize their notification settings:

```sql
-- Insert/update preferences
INSERT INTO user_notification_preferences (
    user_id,
    email_enabled,
    digest_time,
    minimum_announcements
) VALUES (
    'USER_ID_HERE',
    true,
    '18:00:00',
    3  -- Only send if 3+ announcements
) ON CONFLICT (user_id) DO UPDATE SET
    email_enabled = EXCLUDED.email_enabled,
    minimum_announcements = EXCLUDED.minimum_announcements;

-- Disable emails for a user
UPDATE user_notification_preferences
SET email_enabled = FALSE
WHERE user_id = 'USER_ID_HERE';
```

---

## 🎨 Customization

### Change Email Frequency

Edit cron schedule:
- Daily: `0 18 * * *`
- Every 6 hours: `0 */6 * * *`
- Weekdays only: `0 18 * * 1-5`
- Twice daily: `0 9,18 * * *`

### Customize Email Content

Edit `generate_combined_digest_html()` in `send_daily_digest.py`:
- Add company logos
- Include stock prices
- Add charts/graphs
- Customize colors
- Add more metadata

### Add SMS Notifications

1. Install Twilio: `pip install twilio`
2. Add phone number check in `send_digest_to_user()`
3. Send SMS for high-priority announcements
4. Update user preferences to include SMS settings

---

## 📞 Support

### Common Questions

**Q: Can I send emails immediately instead of daily?**
A: Yes, remove the cron job and call the digest sender from the API endpoint directly. Not recommended due to spam concerns.

**Q: How do I change the email time?**
A: Update the cron schedule time. For timezones, ensure server time is correct.

**Q: Can users unsubscribe?**
A: Yes, add an unsubscribe endpoint that sets `email_enabled = FALSE` in preferences.

**Q: What if Resend is down?**
A: Notifications remain in queue (is_processed = FALSE) and will be retried next day.

### Get Help

- Check logs: `/var/log/backfin/digest_*.log`
- Run test suite: `python3 scripts/test_digest_system.py`
- Database issues: Check Supabase dashboard
- Email issues: Check Resend dashboard

---

## ✅ Deployment Checklist

Before going to production:

- [ ] Run test suite successfully
- [ ] Send test email to yourself
- [ ] Verify email rendering on desktop
- [ ] Verify email rendering on mobile
- [ ] Check spam score (use mail-tester.com)
- [ ] Test with 5-10 real users
- [ ] Monitor logs for 3 days
- [ ] Set up monitoring alerts
- [ ] Document any custom changes
- [ ] Schedule cron job
- [ ] Add monitoring dashboard

---

## 🎯 Success Metrics

After 30 days, measure:
- Email delivery rate (should be >95%)
- Open rate (target >20%)
- Click-through rate (target >10%)
- User complaints (should be <1%)
- Processing time (should be <10 minutes)

Query metrics:
```sql
-- Email delivery rate
SELECT 
    status,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
FROM user_email_digest_log
WHERE digest_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY status;

-- Average processing time (add timing to script)
-- Average emails per user
SELECT AVG(announcement_count) as avg_announcements
FROM user_email_digest_log
WHERE status = 'sent'
AND digest_date >= CURRENT_DATE - INTERVAL '30 days';
```

---

**Last Updated:** 29 November 2025  
**Version:** 1.0  
**Maintainer:** Backfin Team
