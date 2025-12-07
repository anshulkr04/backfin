# Daily Digest System - Quick Reference

## 🚀 Quick Commands

```bash
# Test the system
python3 scripts/test_digest_system.py

# Dry run (no emails sent)
python3 scripts/send_daily_digest.py --dry-run

# Send to one user (testing)
python3 scripts/send_daily_digest.py --test-user USER_ID

# Send to all users (production)
python3 scripts/send_daily_digest.py

# Manual send to specific email
python3 scripts/manual_send_digest.py user@example.com

# Send for past date
python3 scripts/send_daily_digest.py --date 2025-11-28
```

## 📊 Useful SQL Queries

```sql
-- Pending notifications count
SELECT COUNT(*) FROM user_notification_queue 
WHERE is_processed = FALSE;

-- Today's stats
SELECT 
    COUNT(DISTINCT user_id) as users,
    COUNT(*) as notifications
FROM user_notification_queue
WHERE notification_date = CURRENT_DATE
AND is_processed = FALSE;

-- Email delivery status
SELECT status, COUNT(*) 
FROM user_email_digest_log
WHERE digest_date = CURRENT_DATE
GROUP BY status;

-- Failed emails today
SELECT user_id, email_address, error_message
FROM user_email_digest_log
WHERE digest_date = CURRENT_DATE
AND status = 'failed';

-- Top companies by notification count
SELECT company_name, COUNT(*) as count
FROM user_notification_queue
WHERE notification_date = CURRENT_DATE
GROUP BY company_name
ORDER BY count DESC
LIMIT 10;
```

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| No emails sent | Check `python3 scripts/test_digest_system.py` |
| Script crashes | Check logs: `tail -f /var/log/backfin/digest_*.log` |
| Wrong email content | Update `generate_combined_digest_html()` |
| Cron not running | Check: `crontab -l` and `grep CRON /var/log/syslog` |
| Resend errors | Verify API key and domain in Resend dashboard |

## 📁 File Locations

```
backfin/
├── api/app.py                        # API endpoint (updated)
├── scripts/
│   ├── send_daily_digest.py          # Main digest sender
│   ├── test_digest_system.py         # Test suite
│   ├── manual_send_digest.py         # Manual sender
│   ├── DIGEST_SETUP_GUIDE.md         # Full documentation
│   └── DIGEST_QUICK_REFERENCE.md     # This file
├── src/services/
│   └── notification_service.py       # Email templates
└── logs/
    └── digest_YYYY-MM-DD.log         # Daily logs
```

## ⚙️ Environment Variables

```bash
# Required in .env file
SUPABASE_URL2=https://xxx.supabase.co
SUPABASE_KEY2=xxx
RESEND_API=re_xxx
APP_BASE_URL=https://backfin.com  # Optional
```

## 📅 Cron Setup (Daily at 6 PM)

```bash
# Edit crontab
crontab -e

# Add this line
0 18 * * * cd /Users/anshulkumar/backfin && /usr/bin/python3 scripts/send_daily_digest.py >> /var/log/backfin/digest_cron.log 2>&1
```

## 🎯 Key Metrics

```sql
-- Success rate
SELECT 
    status,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
FROM user_email_digest_log
WHERE digest_date >= CURRENT_DATE - 7
GROUP BY status;

-- Average announcements per user
SELECT AVG(announcement_count)
FROM user_email_digest_log
WHERE status = 'sent'
AND digest_date >= CURRENT_DATE - 7;
```

## 🔄 Workflow

```
1. Announcement arrives → API queues notification
2. End of day → Cron runs send_daily_digest.py
3. Script fetches pending → Groups by user & company
4. Generates HTML email → Sends via Resend
5. Updates database → Marks as processed
6. Logs result → Available for analytics
```

## 📧 Email Status Values

- `pending` - Queued but not sent yet
- `sent` - Successfully delivered
- `failed` - Delivery failed (see error_message)
- `skipped` - User preferences or no email

## 🛠️ Development Tips

```bash
# Watch logs in real-time
tail -f /var/log/backfin/digest_$(date +%Y-%m-%d).log

# Count successes today
grep "✅ Email sent" /var/log/backfin/digest_$(date +%Y-%m-%d).log | wc -l

# Find errors
grep "❌" /var/log/backfin/digest_*.log

# Test email template locally
python3 -c "
from scripts.send_daily_digest import generate_combined_digest_html
# ... test code
"
```

## 📞 Emergency Commands

```bash
# Stop cron temporarily
crontab -l > /tmp/cron_backup
crontab -r  # Remove all cron jobs

# Restore cron
crontab /tmp/cron_backup

# Clear pending notifications (DANGER!)
# Use with caution - this deletes unprocessed notifications
# UPDATE user_notification_queue SET is_processed = TRUE WHERE notification_date = CURRENT_DATE;

# Reprocess failed emails
python3 scripts/send_daily_digest.py --date $(date +%Y-%m-%d)
```

## ✅ Health Check

Run this weekly:

```bash
# 1. Check cron is running
crontab -l | grep send_daily_digest

# 2. Check recent logs
ls -lh /var/log/backfin/ | tail -5

# 3. Check database
psql -c "SELECT COUNT(*) FROM user_notification_queue WHERE is_processed = FALSE;"

# 4. Check email status
psql -c "SELECT status, COUNT(*) FROM user_email_digest_log WHERE digest_date >= CURRENT_DATE - 7 GROUP BY status;"

# 5. Run test suite
python3 scripts/test_digest_system.py
```

---

**Quick Help:**
- Full docs: `scripts/DIGEST_SETUP_GUIDE.md`
- Architecture: `WATCHLIST_NOTIFICATION_ARCHITECTURE.md`
- Issues: Check logs and run test suite first
