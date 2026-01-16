#!/bin/bash
# Helper script to manage the Backfin cron service

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

PID_FILE="logs/cron.pid"
LOG_FILE="logs/cron.log"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
start_service() {
    if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Service is already running (PID: $(cat $PID_FILE))${NC}"
        return 1
    fi
    
    echo -e "${BLUE}Starting Backfin Cron Manager...${NC}"
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Start in background
    nohup python3 daily_cron_manager.py >> "$LOG_FILE" 2>&1 &
    
    # Save PID
    echo $! > "$PID_FILE"
    
    sleep 2
    
    if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Service started successfully (PID: $(cat $PID_FILE))${NC}"
        echo -e "${BLUE}Logs: tail -f $LOG_FILE${NC}"
    else
        echo -e "${RED}❌ Failed to start service${NC}"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_service() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${YELLOW}⚠️  Service is not running (no PID file)${NC}"
        return 1
    fi
    
    PID=$(cat "$PID_FILE")
    
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Service is not running (stale PID file)${NC}"
        rm -f "$PID_FILE"
        return 1
    fi
    
    echo -e "${BLUE}Stopping Backfin Cron Manager (PID: $PID)...${NC}"
    kill "$PID"
    
    # Wait for process to stop
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            rm -f "$PID_FILE"
            echo -e "${GREEN}✅ Service stopped successfully${NC}"
            return 0
        fi
        sleep 1
    done
    
    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Force killing process...${NC}"
        kill -9 "$PID"
        sleep 1
    fi
    
    rm -f "$PID_FILE"
    echo -e "${GREEN}✅ Service stopped${NC}"
}

status_service() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${RED}❌ Service is not running${NC}"
        return 1
    fi
    
    PID=$(cat "$PID_FILE")
    
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Service is running (PID: $PID)${NC}"
        echo ""
        echo "Process info:"
        ps -p "$PID" -o pid,ppid,etime,cmd
        echo ""
        echo "Logs: tail -f $LOG_FILE"
        return 0
    else
        echo -e "${RED}❌ Service is not running (stale PID file)${NC}"
        rm -f "$PID_FILE"
        return 1
    fi
}

restart_service() {
    echo -e "${BLUE}Restarting Backfin Cron Manager...${NC}"
    stop_service || true
    sleep 2
    start_service
}

show_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}⚠️  No log file found${NC}"
        return 1
    fi
    
    if [ "$1" == "follow" ] || [ "$1" == "f" ]; then
        tail -f "$LOG_FILE"
    else
        tail -n 50 "$LOG_FILE"
    fi
}

test_job() {
    if [ -z "$1" ]; then
        echo -e "${RED}❌ Please specify a job to test${NC}"
        echo "Available jobs: corporate_actions, deals, insider_trading, watchlist_digest, all_data"
        return 1
    fi
    
    source .venv/bin/activate
    python3 daily_cron_manager.py --test "$1"
}

# Main
case "$1" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        status_service
        ;;
    logs)
        show_logs "$2"
        ;;
    test)
        test_job "$2"
        ;;
    *)
        echo "Backfin Cron Manager Control Script"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|logs|test}"
        echo ""
        echo "Commands:"
        echo "  start              Start the cron manager in background"
        echo "  stop               Stop the cron manager"
        echo "  restart            Restart the cron manager"
        echo "  status             Check if cron manager is running"
        echo "  logs [follow]      Show logs (use 'follow' to tail)"
        echo "  test <job_name>    Test a specific job"
        echo ""
        echo "Test jobs:"
        echo "  corporate_actions  Test corporate actions collection"
        echo "  deals              Test deals collection"
        echo "  insider_trading    Test insider trading collection"
        echo "  watchlist_digest   Test watchlist digest emails"
        echo "  all_data           Test all data collections"
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 status"
        echo "  $0 logs follow"
        echo "  $0 test corporate_actions"
        echo "  $0 stop"
        echo ""
        exit 1
        ;;
esac
