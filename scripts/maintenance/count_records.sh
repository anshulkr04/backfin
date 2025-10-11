#!/usr/bin/env bash
# count.sh - Fixed, safe version
# Analyze ./data/bse_raw.db and print metrics + filtered problem tables.
# Usage examples:
#   ./count.sh                       # show metrics and all 3 problem tables
#   ./count.sh -d 2025-09-21 -down   # date + not-downloaded
#   ./count.sh -proc -supa           # not-processed AND not-sent intersection shown too
set -euo pipefail

DB_PATH="./data/bse_raw.db"
DATE_FILTER=""
SHOW_DOWN=0
SHOW_PROC=0
SHOW_SUPA=0
HELP=0

# parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--date)
      DATE_FILTER="$2"
      shift 2
      ;;
    -down)
      SHOW_DOWN=1
      shift
      ;;
    -proc)
      SHOW_PROC=1
      shift
      ;;
    -supa)
      SHOW_SUPA=1
      shift
      ;;
    -h|--help)
      HELP=1
      shift
      ;;
    --db)
      DB_PATH="$2"; shift 2
      ;;
    *)
      echo "Unknown arg: $1"
      echo "Use -h for help."
      exit 1
      ;;
  esac
done

if [[ "$HELP" -eq 1 ]]; then
  cat <<EOF
Usage: $0 [--db PATH] [-d YYYY-MM-DD] [-down] [-proc] [-supa]

  -d YYYY-MM-DD    Filter to that fetched_at date (matches date(fetched_at))
  -down            Show rows where downloaded_pdf_file is NULL or empty
  -proc            Show rows where ai_processed = 0 or NULL
  -supa            Show rows where sent_to_supabase = 0 or NULL

If none of -down/-proc/-supa are provided, all three "problem" tables will be shown.
You can combine flags to show rows matching all selected criteria (AND).
EOF
  exit 0
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "Error: sqlite3 CLI not installed."
  exit 2
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "Error: DB not found at '$DB_PATH'"
  exit 3
fi

# Validate date if provided
if [[ -n "$DATE_FILTER" ]]; then
  if ! [[ "$DATE_FILTER" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "Error: date must be in YYYY-MM-DD format"
    exit 4
  fi
  BASE_WHERE="WHERE date(fetched_at) = '$DATE_FILTER'"
else
  BASE_WHERE=""
fi

# Helper to run a single-count query and return the number
run_count_query() {
  local sql="$1"
  sqlite3 -readonly "$DB_PATH" "$sql"
}

# Counts (respecting date filter for announcements; for raw_responses we apply the same date filter if provided)
if [[ -n "$BASE_WHERE" ]]; then
  COUNT_RAW=$(run_count_query "SELECT COUNT(*) FROM raw_responses WHERE date(fetched_at) = '$DATE_FILTER';")
  COUNT_ANNOUNCEMENTS=$(run_count_query "SELECT COUNT(*) FROM announcements WHERE date(fetched_at) = '$DATE_FILTER';")
  COUNT_DOWNLOADED=$(run_count_query "SELECT COUNT(*) FROM announcements WHERE date(fetched_at) = '$DATE_FILTER' AND (downloaded_pdf_file IS NOT NULL AND TRIM(downloaded_pdf_file) != '');")
  COUNT_AIPROCESSED=$(run_count_query "SELECT COUNT(*) FROM announcements WHERE date(fetched_at) = '$DATE_FILTER' AND (ai_processed = 1);")
  COUNT_SENT=$(run_count_query "SELECT COUNT(*) FROM announcements WHERE date(fetched_at) = '$DATE_FILTER' AND (sent_to_supabase = 1);")
else
  COUNT_RAW=$(run_count_query "SELECT COUNT(*) FROM raw_responses;")
  COUNT_ANNOUNCEMENTS=$(run_count_query "SELECT COUNT(*) FROM announcements;")
  COUNT_DOWNLOADED=$(run_count_query "SELECT COUNT(*) FROM announcements WHERE (downloaded_pdf_file IS NOT NULL AND TRIM(downloaded_pdf_file) != '');")
  COUNT_AIPROCESSED=$(run_count_query "SELECT COUNT(*) FROM announcements WHERE (ai_processed = 1);")
  COUNT_SENT=$(run_count_query "SELECT COUNT(*) FROM announcements WHERE (sent_to_supabase = 1);")
fi

# Print top metrics
echo
echo "===== BSE DB Summary ($DB_PATH) ====="
if [[ -n "$DATE_FILTER" ]]; then
  echo "Date filter: $DATE_FILTER"
fi
printf "Total raw_responses ...... %10s\n" "$COUNT_RAW"
printf "Total announcements ...... %10s\n" "$COUNT_ANNOUNCEMENTS"
printf "PDFs downloaded .......... %10s\n" "$COUNT_DOWNLOADED"
printf "AI processed ............. %10s\n" "$COUNT_AIPROCESSED"
printf "Sent to Supabase .......... %10s\n" "$COUNT_SENT"
echo "========================================"
echo

# Default to showing all problem tables if none specified
if [[ $SHOW_DOWN -eq 0 && $SHOW_PROC -eq 0 && $SHOW_SUPA -eq 0 ]]; then
  SHOW_DOWN=1
  SHOW_PROC=1
  SHOW_SUPA=1
fi

# Helper to print a table for a given WHERE clause (pass clause WITHOUT leading WHERE)
print_table_for_where() {
  local clause="$1"
  if [[ -n "$clause" ]]; then
    clause="WHERE $clause"
  fi

  sqlite3 -readonly "$DB_PATH" <<SQL
.headers on
.mode column
SELECT
  id,
  COALESCE(newsid,'') AS newsid,
  COALESCE(scrip_cd,'') AS scrip_cd,
  CASE WHEN LENGTH(COALESCE(headline,'')) > 120 THEN SUBSTR(headline,1,117) || '...' ELSE headline END AS headline,
  COALESCE(downloaded_pdf_file,'') AS pdf_file,
  COALESCE(pdf_pages,'') AS pdf_pages,
  COALESCE(ai_processed,0) AS ai_processed,
  COALESCE(sent_to_supabase,0) AS sent_to_supabase,
  COALESCE(fetched_at,'') AS fetched_at
FROM announcements
${clause}
ORDER BY CASE WHEN fetched_at IS NOT NULL AND fetched_at != '' THEN fetched_at ELSE printf('%010d', id) END DESC
LIMIT 500;
SQL
}

# Print tables per requested filters (individual tables)
if [[ $SHOW_DOWN -eq 1 ]]; then
  echo "=== Announcements: PDF NOT downloaded ==="
  if [[ -n "$BASE_WHERE" ]]; then
    print_table_for_where "date(fetched_at) = '$DATE_FILTER' AND (downloaded_pdf_file IS NULL OR TRIM(downloaded_pdf_file) = '')"
  else
    print_table_for_where "(downloaded_pdf_file IS NULL OR TRIM(downloaded_pdf_file) = '')"
  fi
  echo
fi

if [[ $SHOW_PROC -eq 1 ]]; then
  echo "=== Announcements: NOT AI-processed (ai_processed = 0 or NULL) ==="
  if [[ -n "$BASE_WHERE" ]]; then
    print_table_for_where "date(fetched_at) = '$DATE_FILTER' AND (ai_processed = 0 OR ai_processed IS NULL)"
  else
    print_table_for_where "(ai_processed = 0 OR ai_processed IS NULL)"
  fi
  echo
fi

if [[ $SHOW_SUPA -eq 1 ]]; then
  echo "=== Announcements: NOT sent to Supabase (sent_to_supabase = 0 or NULL) ==="
  if [[ -n "$BASE_WHERE" ]]; then
    print_table_for_where "date(fetched_at) = '$DATE_FILTER' AND (sent_to_supabase = 0 OR sent_to_supabase IS NULL)"
  else
    print_table_for_where "(sent_to_supabase = 0 OR sent_to_supabase IS NULL)"
  fi
  echo
fi

# If more than one flag selected, print intersection (rows matching ALL selected negative conditions)
NUM_FLAGS=$((SHOW_DOWN + SHOW_PROC + SHOW_SUPA))
if [[ $NUM_FLAGS -gt 1 ]]; then
  echo "=== Intersection: announcements matching ALL selected conditions ==="
  parts=()
  if [[ -n "$DATE_FILTER" ]]; then
    parts+=("date(fetched_at) = '$DATE_FILTER'")
  fi
  if [[ $SHOW_DOWN -eq 1 ]]; then
    parts+=("(downloaded_pdf_file IS NULL OR TRIM(downloaded_pdf_file) = '')")
  fi
  if [[ $SHOW_PROC -eq 1 ]]; then
    parts+=("(ai_processed = 0 OR ai_processed IS NULL)")
  fi
  if [[ $SHOW_SUPA -eq 1 ]]; then
    parts+=("(sent_to_supabase = 0 OR sent_to_supabase IS NULL)")
  fi

  # join parts with AND
  combined=""
  for i in "${!parts[@]}"; do
    if [[ $i -eq 0 ]]; then
      combined="${parts[$i]}"
    else
      combined="${combined} AND ${parts[$i]}"
    fi
  done

  print_table_for_where "$combined"
  echo
fi

exit 0
