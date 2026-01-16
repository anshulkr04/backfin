# 🚀 Backfin Daily Cron System - Quick Start Guide

## What This Does

Automatically runs these tasks every day:
- **7:00 PM**: Collect data from NSE & BSE
  - Corporate Actions
  - Bulk & Block Deals  
  - Insider Trading
- **12:00 AM** (Midnight): Send watchlist digest emails to users

## 🛠️ One-Time Setup

```bash
# 1. Run setup script
bash setup_cron.sh

# 2. Test each component (recommended)
python3 daily_cron_manager.py --test corporate_actions
python3 daily_cron_manager.py --test deals
python3 daily_cron_manager.py --test insider_trading
python3 daily_cron_manager.py --test watchlist_digest
```

## 🎯 Daily Usage

### Easy Way (Recommended)
```bash
# Start the cron manager
./manage_cron.sh start

# Check status
./manage_cron.sh status

# View logs
./manage_cron.sh logs follow

# Stop
./manage_cron.sh stop
```

### Manual Way
```bash
# Run in background
nohup python3 daily_cron_manager.py >> logs/cron.log 2>&1 &

# Stop
pkill -f daily_cron_manager.py
```

## 📊 What Happens When?

| Time | Action |
|------|--------|
| 7:00 PM | Scrapes NSE & BSE for corporate actions, deals, insider trading |
| 12:00 AM | Sends digest emails to all users with watchlist updates |

## 📁 Where Are Logs?

- Main logs: `logs/cron/cron_manager_YYYYMMDD.log`
- Individual service logs in: `logs/queues/`, `logs/system/`, `logs/workers/`

## 🧪 Testing Before Going Live

```bash
# Test individual components
./manage_cron.sh test corporate_actions
./manage_cron.sh test deals
./manage_cron.sh test insider_trading
./manage_cron.sh test watchlist_digest

# Test all data collection at once
./manage_cron.sh test all_data
```

## 🔍 Monitoring

```bash
# Check if running
./manage_cron.sh status

# Watch logs in real-time
./manage_cron.sh logs follow

# Check last 50 lines
./manage_cron.sh logs
```

## 🚨 Troubleshooting

### Service won't start
1. Check if already running: `./manage_cron.sh status`
2. Check logs: `./manage_cron.sh logs`
3. Verify `.env` file has: `SUPABASE_URL2`, `SUPABASE_KEY2`, `RESEND_API_KEY`

### Jobs not running at scheduled time
1. Verify service is running: `./manage_cron.sh status`
2. Check system time: `date`
3. Review logs for errors: `./manage_cron.sh logs`

### Data not being collected
1. Test individual job: `./manage_cron.sh test corporate_actions`
2. Check database connectivity
3. Verify API credentials in `.env`

## 📦 Historical Data Collection

To backfill data from Nov 25, 2025 to today:

```bash
# Corporate Actions
python3 collect_historical_corporate_actions.py

# Deals
python3 collect_historical_deals.py

# Insider Trading
python3 collect_historical_insider_trading.py
```

## 🔄 Updating

If you update the code:

```bash
# Restart the service
./manage_cron.sh restart
```

## 💡 Pro Tips

1. **Run in screen/tmux** for better session management:
   ```bash
   screen -S backfin-cron
   python3 daily_cron_manager.py
   # Ctrl+A, D to detach
   ```

2. **Set up log rotation** to prevent logs from growing too large:
   ```bash
   # Add to /etc/logrotate.d/backfin
   /Users/anshulkumar/backfin/logs/*.log {
       daily
       rotate 30
       compress
       missingok
       notifempty
   }
   ```

3. **Monitor with systemd** (Linux only):
   ```bash
   # See CRON_MANAGER_README.md for systemd setup
   sudo systemctl status backfin-cron
   ```

## 📞 Need Help?

1. Check `CRON_MANAGER_README.md` for detailed documentation
2. Review logs in `logs/cron/` directory
3. Test individual components to isolate issues

---

**Created**: January 2026  
**Last Updated**: January 16, 2026
