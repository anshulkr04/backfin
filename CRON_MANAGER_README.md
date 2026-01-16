# Daily Cron Manager - Quick Reference

## Overview
The `daily_cron_manager.py` script manages two scheduled tasks:
- **Data Collection** (7:00 PM): Corporate Actions, Deals, Insider Trading
- **Watchlist Digest** (12:00 AM): Email notifications to users

## Installation

```bash
# Run setup script
bash setup_cron.sh
```

## Testing Jobs

Test each job individually before starting the scheduler:

```bash
# Test corporate actions collection
python3 daily_cron_manager.py --test corporate_actions

# Test deals collection
python3 daily_cron_manager.py --test deals

# Test insider trading collection
python3 daily_cron_manager.py --test insider_trading

# Test watchlist digest emails
python3 daily_cron_manager.py --test watchlist_digest

# Test all data collections
python3 daily_cron_manager.py --test all_data
```

## Running the Scheduler

### Option 1: Foreground (for testing)
```bash
python3 daily_cron_manager.py
```

### Option 2: Background with nohup
```bash
# Start in background
nohup python3 daily_cron_manager.py >> logs/cron.log 2>&1 &

# Save the process ID
echo $! > logs/cron.pid

# Check if running
ps -p $(cat logs/cron.pid)

# Stop the process
kill $(cat logs/cron.pid)
```

### Option 3: System Service (recommended for production)

Create `/etc/systemd/system/backfin-cron.service`:

```ini
[Unit]
Description=Backfin Daily Data Collection and Notification Service
After=network.target

[Service]
Type=simple
User=anshulkumar
WorkingDirectory=/Users/anshulkumar/backfin
Environment="PATH=/Users/anshulkumar/backfin/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/Users/anshulkumar/backfin/.venv/bin/python3 /Users/anshulkumar/backfin/daily_cron_manager.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/backfin/cron.log
StandardError=append:/var/log/backfin/cron_error.log

[Install]
WantedBy=multi-user.target
```

Then:
```bash
# Create log directory
sudo mkdir -p /var/log/backfin
sudo chown anshulkumar:anshulkumar /var/log/backfin

# Enable and start service
sudo systemctl enable backfin-cron.service
sudo systemctl start backfin-cron.service

# Check status
sudo systemctl status backfin-cron.service

# View logs
sudo journalctl -u backfin-cron.service -f
```

## Schedule Details

| Job | Time | Description |
|-----|------|-------------|
| Data Collection | 7:00 PM | Collects Corporate Actions, Deals, and Insider Trading data from NSE and BSE |
| Watchlist Digest | 12:00 AM | Sends daily digest emails to users with watchlist updates |

## Logs

Logs are stored in:
- `logs/cron/cron_manager_YYYYMMDD.log` - Main cron manager logs
- `logs/cron.log` - Output when running with nohup
- Individual service logs in their respective directories

## Monitoring

Check if the scheduler is running:
```bash
# If using nohup
ps -p $(cat logs/cron.pid)

# If using systemd
sudo systemctl status backfin-cron.service

# View recent logs
tail -f logs/cron/cron_manager_$(date +%Y%m%d).log
```

## Troubleshooting

### Jobs not running at scheduled time
1. Check system time: `date`
2. Verify timezone: `timedatectl` (Linux) or `date` (macOS)
3. Check logs for errors: `tail -f logs/cron/cron_manager_*.log`

### Missing dependencies
```bash
# Reinstall dependencies
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment variables not set
1. Verify `.env` file exists in project root
2. Check required variables:
   - `SUPABASE_URL2`
   - `SUPABASE_KEY2`
   - `RESEND_API_KEY`

### Job failed with exception
1. Check specific job logs in `logs/` directory
2. Test job individually: `python3 daily_cron_manager.py --test <job_name>`
3. Review error traceback in logs

## Historical Data Collection

To collect historical data from Nov 25, 2025 to today:

```bash
# Corporate Actions
python3 collect_historical_corporate_actions.py

# Deals
python3 collect_historical_deals.py

# Insider Trading
python3 collect_historical_insider_trading.py
```

These scripts iterate day-by-day and handle deduplication automatically.

## Architecture

```
daily_cron_manager.py
├── APScheduler (manages timing)
├── Data Collection Job (7:00 PM)
│   ├── Corporate Actions
│   │   └── src/services/exchange_data/corporate_actions/corporate_actions_collector.py
│   ├── Deals
│   │   └── src/services/exchange_data/deals_management/deals_detector.py
│   └── Insider Trading
│       └── src/services/exchange_data/insider_trading/insider_trading_detector.py
└── Watchlist Digest Job (12:00 AM)
    └── scripts/send_daily_digest.py
```

## Dependencies

- Python 3.8+
- APScheduler 3.10+
- All dependencies from `requirements.txt`

## Support

For issues:
1. Check logs first
2. Test individual jobs
3. Verify environment variables
4. Check database connectivity
