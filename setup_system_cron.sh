#!/bin/bash
# Setup system-level cron jobs for Backfin data collection
# Run this script on your VM to set up automated data collection

set -e

echo "🔧 Backfin System Cron Setup"
echo "============================="
echo ""

# Get the absolute path to the backfin directory
BACKFIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="/usr/bin/python3"

echo "📁 Backfin directory: $BACKFIN_DIR"
echo "🐍 Python binary: $PYTHON_BIN"
echo ""

# Install Python dependencies on host
echo "📦 Installing Python dependencies..."
pip3 install apscheduler python-dotenv supabase pandas requests selenium webdriver-manager

# Install Chrome/Chromium for BSE scraper
echo "🌐 Installing Chromium for Selenium..."
apt-get update
apt-get install -y chromium-browser chromium-chromedriver wget unzip

# Set ChromeDriver path
export CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Create log directory
mkdir -p /var/log/backfin
mkdir -p $BACKFIN_DIR/logs/cron

echo ""
echo "✅ Dependencies installed"
echo ""

# Create wrapper scripts for each cron job
echo "📝 Creating cron wrapper scripts..."

# 1. Corporate Actions & Deals (7 PM daily)
cat > /usr/local/bin/backfin-daily-data <<'EOF'
#!/bin/bash
cd /root/backfin
export CHROMEDRIVER_PATH=/usr/bin/chromedriver
/usr/bin/python3 daily_cron_manager.py --test corporate_actions >> /var/log/backfin/daily-data.log 2>&1
/usr/bin/python3 daily_cron_manager.py --test deals >> /var/log/backfin/daily-data.log 2>&1
EOF

# 2. Insider Trading (every hour)
cat > /usr/local/bin/backfin-insider-trading <<'EOF'
#!/bin/bash
cd /root/backfin
export CHROMEDRIVER_PATH=/usr/bin/chromedriver
/usr/bin/python3 daily_cron_manager.py --test insider_trading >> /var/log/backfin/insider-trading.log 2>&1
EOF

# 3. Watchlist Digest (midnight)
cat > /usr/local/bin/backfin-watchlist-digest <<'EOF'
#!/bin/bash
cd /root/backfin
/usr/bin/python3 daily_cron_manager.py --test watchlist_digest >> /var/log/backfin/watchlist-digest.log 2>&1
EOF

# Make scripts executable
chmod +x /usr/local/bin/backfin-daily-data
chmod +x /usr/local/bin/backfin-insider-trading
chmod +x /usr/local/bin/backfin-watchlist-digest

echo "✅ Created wrapper scripts:"
echo "   - /usr/local/bin/backfin-daily-data"
echo "   - /usr/local/bin/backfin-insider-trading"
echo "   - /usr/local/bin/backfin-watchlist-digest"
echo ""

# Add cron jobs
echo "⏰ Setting up cron jobs..."

# Create temporary crontab
TEMP_CRON=$(mktemp)

# Export existing crontab (if any)
crontab -l > $TEMP_CRON 2>/dev/null || true

# Remove old backfin cron entries
sed -i '/backfin/d' $TEMP_CRON

# Add new cron entries
cat >> $TEMP_CRON <<'EOF'

# Backfin Data Collection Cron Jobs
# Corporate Actions & Deals - 7:00 PM daily
0 19 * * * /usr/local/bin/backfin-daily-data

# Insider Trading - Every hour
0 * * * * /usr/local/bin/backfin-insider-trading

# Watchlist Digest Emails - Midnight
0 0 * * * /usr/local/bin/backfin-watchlist-digest

EOF

# Install new crontab
crontab $TEMP_CRON
rm $TEMP_CRON

echo "✅ Cron jobs installed"
echo ""

# Show current crontab
echo "📋 Current crontab:"
echo "==================="
crontab -l | grep -A 10 "Backfin"
echo ""

echo "✅ Setup complete!"
echo ""
echo "📊 Schedule Summary:"
echo "  - Corporate Actions & Deals: 7:00 PM daily"
echo "  - Insider Trading: Every hour"
echo "  - Watchlist Digest: 12:00 AM daily"
echo ""
echo "📝 Log files:"
echo "  - Daily data: /var/log/backfin/daily-data.log"
echo "  - Insider trading: /var/log/backfin/insider-trading.log"
echo "  - Watchlist digest: /var/log/backfin/watchlist-digest.log"
echo ""
echo "🔍 Monitor logs:"
echo "  tail -f /var/log/backfin/insider-trading.log"
echo "  tail -f /var/log/backfin/daily-data.log"
echo ""
echo "🛑 To remove cron jobs:"
echo "  crontab -e  # Then delete the Backfin lines"
