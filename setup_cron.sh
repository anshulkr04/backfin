#!/bin/bash
# Setup script for Backfin Daily Cron Manager
# This script installs dependencies and sets up the cron service

set -e  # Exit on error

echo "========================================="
echo "Backfin Daily Cron Manager Setup"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip -q

# Install APScheduler if not already in requirements.txt
echo -e "${YELLOW}Checking dependencies...${NC}"
if ! grep -q "apscheduler" requirements.txt; then
    echo -e "${YELLOW}Adding APScheduler to requirements...${NC}"
    echo "apscheduler==3.10.4" >> requirements.txt
fi

# Install all dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt -q
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create log directories
echo -e "${YELLOW}Creating log directories...${NC}"
mkdir -p logs/cron
mkdir -p logs/queues
mkdir -p logs/system
mkdir -p logs/workers
echo -e "${GREEN}✓ Log directories created${NC}"

# Check .env file
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file not found${NC}"
    echo -e "${YELLOW}Please create .env file with required variables:${NC}"
    echo "  - SUPABASE_URL2"
    echo "  - SUPABASE_KEY2"
    echo "  - RESEND_API_KEY"
    exit 1
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# Make scripts executable
echo -e "${YELLOW}Making scripts executable...${NC}"
chmod +x daily_cron_manager.py
chmod +x collect_historical_corporate_actions.py
chmod +x collect_historical_deals.py
chmod +x collect_historical_insider_trading.py
echo -e "${GREEN}✓ Scripts are executable${NC}"

echo ""
echo "========================================="
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Test individual jobs:"
echo "   python3 daily_cron_manager.py --test corporate_actions"
echo "   python3 daily_cron_manager.py --test deals"
echo "   python3 daily_cron_manager.py --test insider_trading"
echo "   python3 daily_cron_manager.py --test watchlist_digest"
echo ""
echo "2. Run historical data collection (optional):"
echo "   python3 collect_historical_corporate_actions.py"
echo "   python3 collect_historical_deals.py"
echo "   python3 collect_historical_insider_trading.py"
echo ""
echo "3. Start the cron manager:"
echo "   python3 daily_cron_manager.py"
echo ""
echo "4. Or run in background with nohup:"
echo "   nohup python3 daily_cron_manager.py >> logs/cron.log 2>&1 &"
echo "   echo \$! > logs/cron.pid"
echo ""
echo "5. To stop background process:"
echo "   kill \$(cat logs/cron.pid)"
echo ""
echo "Schedule:"
echo "  📊 Data Collection: 7:00 PM daily"
echo "  📧 Watchlist Digest: 12:00 AM daily"
echo ""
