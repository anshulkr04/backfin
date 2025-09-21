#!/usr/bin/env bash
# count_announcements_today.sh
# Usage:
#   ./count_announcements_today.sh          # counts rows for today's date (local)
#   ./count_announcements_today.sh 2025-09-08   # counts rows for specified date (YYYY-MM-DD)

set -euo pipefail

DB_FILE="${1:-bse_raw.db}"   # default DB file if user passes only date, we'll detect
DATE_ARG=""
# If two args provided, treat first as DB and second as date.
if [ $# -eq 2 ]; then
  DB_FILE="$1"
  DATE_ARG="$2"
elif [ $# -eq 1 ]; then
  # could be either a date or DB file; detect simple date format YYYY-MM-DD
  if [[ "$1" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    DATE_ARG="$1"
    DB_FILE="bse_raw.db"
  else
    DATE_ARG=""
    DB_FILE="$1"
  fi
fi

# If no date provided, compute local today's date in YYYY-MM-DD
if [ -z "$DATE_ARG" ]; then
  # POSIX-compatible date formatting
  TODAY="$(date '+%Y-%m-%d')"
else
  TODAY="$DATE_ARG"
fi

# Validate sqlite3 exists
if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "Error: sqlite3 command not found. Install sqlite3 and try again." >&2
  exit 2
fi

# Check DB file exists
if [ ! -f "$DB_FILE" ]; then
  echo "Error: database file '$DB_FILE' not found." >&2
  exit 3
fi

# Compose SQL - use LIKE 'YYYY-MM-DD%' to match ISO datetime date prefix
SQL="SELECT COUNT(*) AS count FROM announcements WHERE fetched_at LIKE '${TODAY}%';"

# Execute and show result
COUNT=$(sqlite3 "$DB_FILE" "$SQL" 2>/dev/null || {
  echo "Error: failed to query database." >&2
  exit 4
})

echo "Database: $DB_FILE"
echo "Date filter (fetched_at starts with): $TODAY"
echo "Announcements count: $COUNT"
