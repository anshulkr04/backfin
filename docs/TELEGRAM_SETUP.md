# Telegram Notification System Setup Guide

This guide explains how to set up the Telegram notification system for Backfin announcements.

## Overview

The system sends instant Telegram notifications to users when companies in their watchlist publish new announcements.

### Architecture

```
New Announcement → AI Processing → Supabase Upload → Queue Telegram Job
                                                          ↓
                                              Telegram Worker
                                                          ↓
                                              Send to Subscribers
```

### Components

1. **Telegram Bot Service** (`telegram-bot`): Handles user subscription commands
2. **Telegram Notification Worker** (`telegram-worker`): Sends notifications from Redis queue
3. **Redis Queue**: `backfin:queue:telegram_notifications`
4. **Database Tables**: Subscription tracking and notification logs

---

## Step 1: Create Telegram Bot with BotFather

1. Open Telegram and search for `@BotFather`

2. Start a chat and send `/newbot`

3. Follow the prompts:
   - Enter a **name** for your bot (e.g., "Backfin Alerts")
   - Enter a **username** for your bot (must end in `bot`, e.g., `backfin_alerts_bot`)

4. BotFather will give you a **token** like:
   ```
   1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
   ```

5. **Save this token** - you'll need it for the `.env` file

6. (Optional) Configure bot settings:
   ```
   /setdescription - Set bot description
   /setabouttext - Set "About" text
   /setuserpic - Set profile picture
   /setcommands - Set command menu
   ```

7. Set command menu (optional but recommended):
   ```
   /setcommands
   ```
   Then paste:
   ```
   start - Start subscription process
   subscribe - Subscribe to notifications
   unsubscribe - Pause notifications
   status - Check subscription status
   help - Get help
   ```

---

## Step 2: Run Database Migrations

Run the SQL migration file to create required tables:

```bash
# Using psql
psql -h <host> -U <user> -d <database> -f migrations/telegram_notifications.sql

# Or copy-paste the contents into Supabase SQL Editor
```

This creates:
- `user_telegram_subscriptions` - Links Telegram to user accounts
- `telegram_notification_log` - Audit log of all notifications
- `telegram_notification_queue` - Fallback queue (if Redis is down)
- `telegram_bot_stats` - Daily statistics
- Helper functions for subscriber queries

---

## Step 3: Configure Environment Variables

Add these to your `.env` file:

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_BOT_NAME=BackfinBot

# Optional: Webhook mode (for production with HTTPS)
# TELEGRAM_WEBHOOK_URL=https://yourdomain.com/telegram/webhook
```

---

## Step 4: Deploy Services

### Using Docker Compose

The services are already configured in `docker-compose.redis.yml`:

```bash
# Build and start all services including Telegram
docker-compose -f docker-compose.redis.yml up -d --build

# Or just the Telegram services
docker-compose -f docker-compose.redis.yml up -d telegram-bot telegram-worker
```

### Check Service Status

```bash
# Check if services are running
docker-compose -f docker-compose.redis.yml ps

# View logs
docker-compose -f docker-compose.redis.yml logs -f telegram-bot
docker-compose -f docker-compose.redis.yml logs -f telegram-worker
```

---

## Step 5: Test the Bot

1. Open Telegram and search for your bot by username

2. Send `/start`

3. The bot should respond with a welcome message and ask for your email

4. Enter your registered email address

5. You should be subscribed (auto-verified for now)

6. Check status with `/status`

---

## User Subscription Flow

### How Users Subscribe

1. User finds the bot on Telegram (`@your_bot_username`)
2. User sends `/start`
3. Bot asks for registered email
4. User enters email
5. System verifies email exists in UserData table
6. Subscription created and linked to user account
7. User receives confirmation with watchlist count

### How Notifications Work

1. New announcement is processed by AI worker
2. Supabase worker uploads to database
3. After successful upload, notification job is queued to Redis
4. Telegram worker picks up job
5. Worker queries watchlist to find users with this ISIN
6. For each subscriber with matching watchlist entry:
   - Format notification message
   - Send via Telegram Bot API
   - Log delivery status
7. User receives instant notification

---

## Notification Message Format

```
🔔 New Announcement

🏢 Company Name
📌 SYMBOL
📂 Financial Results
📅 2026-01-20

Headline text here...

Summary of the announcement...

💡 Sentiment: 📈 Positive

📄 View Document
🔗 View on Backfin
```

---

## Monitoring & Debugging

### Check Queue Status

```bash
# Connect to Redis
docker exec -it backfin-redis redis-cli

# Check queue length
LLEN backfin:queue:telegram_notifications

# View pending jobs
LRANGE backfin:queue:telegram_notifications 0 10

# Check failed jobs
LLEN backfin:queue:telegram_failed
```

### Check Notification Logs

```sql
-- Recent notifications
SELECT * FROM telegram_notification_log 
ORDER BY created_at DESC 
LIMIT 20;

-- Failed notifications
SELECT * FROM telegram_notification_log 
WHERE notification_status = 'failed'
ORDER BY created_at DESC;

-- Subscription stats
SELECT * FROM telegram_bot_stats 
ORDER BY date DESC 
LIMIT 7;
```

### Check Active Subscriptions

```sql
-- All active subscribers
SELECT 
    ts.telegram_username,
    ts.telegram_chat_id,
    u."emailID",
    ts.notification_count,
    ts.last_notification_at
FROM user_telegram_subscriptions ts
JOIN "UserData" u ON ts.user_id = u."UserID"
WHERE ts.is_active = true AND ts.is_verified = true
ORDER BY ts.subscribed_at DESC;

-- Subscribers for a specific ISIN
SELECT * FROM get_telegram_subscribers_for_isin('INE002A01018');
```

---

## Rate Limiting

Telegram has strict rate limits:
- 30 messages/second per bot (across all chats)
- 1 message/second per chat (average)
- 20 messages/minute per group

The system handles this with:
- Built-in rate limiter (25 msg/sec to stay under limit)
- Retry with exponential backoff on rate limit errors
- Queue-based processing for burst handling

---

## Troubleshooting

### Bot not responding

1. Check bot token is correct in `.env`
2. Check service is running: `docker logs backfin-telegram-bot`
3. Ensure no other instance is running (only one bot can poll at a time)

### Notifications not sending

1. Check worker is running: `docker logs backfin-telegram-worker`
2. Check Redis queue has jobs: `LLEN backfin:queue:telegram_notifications`
3. Verify user has active subscription
4. Check notification logs for errors

### User blocked bot

When a user blocks the bot, notifications will fail with "Forbidden" error.
The system automatically marks these subscriptions as inactive.

### Rate limited

If you see "RetryAfter" errors, you're hitting Telegram's limits.
The worker will automatically wait and retry.

---

## Production Considerations

### Webhook Mode (Recommended for Production)

For production, use webhook mode instead of polling:

1. Set up HTTPS endpoint
2. Configure webhook:
   ```bash
   TELEGRAM_WEBHOOK_URL=https://yourdomain.com/telegram/webhook
   ```
3. Modify bot to use webhook instead of polling

### Scaling

For high volume:
- Run multiple telegram-worker instances (they share the queue)
- Use Redis Cluster for queue scaling
- Consider message batching for popular stocks

### Backup/Fallback

The `telegram_notification_queue` database table serves as a fallback
if Redis is temporarily unavailable. Implement a cron job to retry
failed notifications from this table.

---

## Files Created

```
migrations/
  telegram_notifications.sql    # Database schema

src/services/telegram/
  __init__.py                   # Package exports
  telegram_bot.py               # Bot command handlers
  telegram_notifier.py          # Notification sending logic

workers/
  telegram_notification_worker.py  # Queue consumer worker

docker/
  Dockerfile.telegram-bot       # Bot service container
  Dockerfile.telegram-worker    # Worker container

docker-compose.redis.yml        # Updated with new services
```

---

## Security Notes

1. **Bot Token**: Keep the bot token secret. Never commit to git.
2. **User Verification**: Users must verify their email to subscribe.
3. **Rate Limiting**: Built-in protection against abuse.
4. **Chat IDs**: Store securely, these are user identifiers.

---

## Support

For issues or questions:
- Check logs: `docker logs backfin-telegram-bot`
- Check database: `telegram_notification_log` table
- Contact: support@backfin.in
