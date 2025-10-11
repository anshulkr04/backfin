#!/usr/bin/env bash
# pop.sh
# Create ./data/bse_raw.db (overwrites if exists) and populate with mock data (30 announcements)
set -euo pipefail

DB_DIR="./data"
DB_PATH="$DB_DIR/bse_raw.db"

# ensure sqlite3 exists
if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "Error: sqlite3 CLI is required. Install sqlite3 and retry."
  exit 1
fi

mkdir -p "$DB_DIR"
if [[ -f "$DB_PATH" ]]; then
  echo "Removing existing DB at $DB_PATH"
  rm -f "$DB_PATH"
fi

echo "Creating DB and tables at $DB_PATH"

# Create schema. Use a single sqlite3 invocation and explicit BEGIN/COMMIT for transaction safety.
sqlite3 "$DB_PATH" <<'SQL'
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS raw_responses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fetched_at TEXT NOT NULL,
  url TEXT,
  params TEXT,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS announcements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  newsid TEXT,
  scrip_cd INTEGER,
  headline TEXT,
  fetched_at TEXT NOT NULL,
  raw_json TEXT NOT NULL,
  downloaded_pdf_file TEXT,
  pdf_pages INTEGER,
  pdf_downloaded_at TEXT,
  ai_processed INTEGER DEFAULT 0,
  ai_summary TEXT,
  ai_error TEXT,
  ai_processed_at TEXT,
  sent_to_supabase INTEGER DEFAULT 0,
  sent_to_supabase_at TEXT,
  UNIQUE(newsid)
);

COMMIT;
SQL

echo "Inserting mock raw_responses..."
sqlite3 "$DB_PATH" <<'SQL'
BEGIN TRANSACTION;
INSERT INTO raw_responses(fetched_at, url, params, raw_json) VALUES (datetime('now','-2 hours'), 'https://api.mock/bse1', '{"pageno":1}', '{"Table": [{"NEWSID":"r_raw_1"}]}');
INSERT INTO raw_responses(fetched_at, url, params, raw_json) VALUES (datetime('now','-1 hours'), 'https://api.mock/bse2', '{"pageno":2}', '{"Table": [{"NEWSID":"r_raw_2"}]}');
INSERT INTO raw_responses(fetched_at, url, params, raw_json) VALUES (datetime('now'), 'https://api.mock/bse3', '{"pageno":3}', '{"Table": [{"NEWSID":"r_raw_3"}]}');
COMMIT;
SQL

echo "Inserting 30 mock announcements (varied edge cases)..."

# Use INSERT OR IGNORE to avoid UNIQUE constraint failures aborting the transaction.
sqlite3 "$DB_PATH" <<'SQL'
BEGIN TRANSACTION;

-- 1: normal, pdf downloaded, ai processed, sent
INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, pdf_pages, pdf_downloaded_at, ai_processed, ai_summary, ai_error, ai_processed_at, sent_to_supabase, sent_to_supabase_at)
VALUES ('news_001', 1001, 'Company A: Quarterly results announced', datetime('now','-7 days'), '{"mock":"row1"}', 'corp_a_q1.pdf', 12, datetime('now','-7 days','+1 minute'), 1, 'Net profit increased by 12%', NULL, datetime('now','-7 days','+2 minutes'), 1, datetime('now','-7 days','+5 minutes'));

-- 2: no PDF, procedural
INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, pdf_pages, ai_processed, sent_to_supabase)
VALUES ('news_002', 1002, 'Company B: Trading Window Open', datetime('now','-6 days'), '{"mock":"row2"}', NULL, NULL, 0, 0);

-- 3: PDF present but AI had error
INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, pdf_pages, pdf_downloaded_at, ai_processed, ai_summary, ai_error, ai_processed_at, sent_to_supabase)
VALUES ('news_003', 1003, 'Company C: Complex filing (large PDF)', datetime('now','-6 days','-3 hours'), '{"mock":"row3"}', 'comp_c_report.pdf', 250, datetime('now','-6 days','-2 hours'), 0, NULL, 'AI timeout / file too large', datetime('now','-6 days','-1 hour'), 0);

-- 4: duplicate newsid (same as news_001) - INSERT OR IGNORE will skip
INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json)
VALUES ('news_001', 1001, 'Company A Duplicate: same newsid', datetime('now','-6 days'), '{"mock":"row4"}');

-- 5: missing newsid (NULL)
INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file)
VALUES (NULL, 1004, 'Company D: No newsid provided', datetime('now','-5 days'), '{"mock":"row5"}', 'company_d_doc.pdf');

-- 6: empty strings for some fields
INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, ai_processed)
VALUES ('', NULL, '', datetime('now','-5 days','-1 hour'), '{}', NULL, 0);

-- 7..15: mixed normal rows
INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, pdf_pages, pdf_downloaded_at, ai_processed, ai_summary, ai_processed_at, sent_to_supabase, sent_to_supabase_at)
VALUES ('news_004', 2001, 'Company E: Acquisition announced', datetime('now','-4 days'), '{"mock":"row7"}', 'e_acq.pdf', 6, datetime('now','-4 days','+10 minutes'), 1, 'Acquisition by X - neutral to positive', datetime('now','-4 days','+12 minutes'), 1, datetime('now','-4 days','+30 minutes'));

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, pdf_pages, ai_processed, ai_summary, ai_processed_at)
VALUES ('news_005', 2002, 'Company F: Board Meeting outcome', datetime('now','-3 days'), '{"mock":"row8"}', 'f_board.pdf', 3, 1, 'Outcome approved', datetime('now','-3 days','+5 minutes'));

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, ai_processed)
VALUES ('news_006', 2003, 'Company G: Dividend Declared', datetime('now','-3 days','-2 hours'), '{"mock":"row9"}', 1);

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json)
VALUES ('news_007', 2004, 'Company H: Change in Compliance Officer', datetime('now','-2 days'), '{"mock":"row10"}');

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, pdf_pages)
VALUES ('news_008', 2005, 'Company I: Annual Report', datetime('now','-2 days','-3 hours'), '{"mock":"row11"}', 'i_annual.pdf', 88);

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, ai_processed, ai_summary)
VALUES ('news_009', 2006, 'Company J: Share Buyback', datetime('now','-1 days'), '{"mock":"row12"}', 1, 'Plan for buyback announced');

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, pdf_pages, ai_processed, ai_summary, sent_to_supabase)
VALUES ('news_010', 2007, 'Company K: Rights Issue', datetime('now','-1 days','-2 hours'), '{"mock":"row13"}', 'k_rights.pdf', 20, 1, 'Rights issue details summarized', 0);

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, ai_processed, ai_error)
VALUES ('news_011', 2008, 'Company L: Miscellaneous', datetime('now','-12 hours'), '{"mock":"row14"}', 0, 'Parsing error: unexpected format');

-- 16..20: more variety
INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, sent_to_supabase, sent_to_supabase_at)
VALUES ('news_012', 3001, 'Company M: Filing uploaded manually', datetime('now','-10 hours'), '{"mock":"row15"}', 1, datetime('now','-9 hours'));

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, ai_processed, ai_summary, ai_processed_at)
VALUES ('news_013', 3002, 'Company N: Financial results', datetime('now','-9 hours'), '{"mock":"row16"}', 1, 'Revenue up 5%', datetime('now','-8 hours'));

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, pdf_pages)
VALUES ('news_014', 3003, 'Company O: Regulatory filing', datetime('now','-8 hours'), '{"mock":"row17"}', 'o_reg.pdf', 1);

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, pdf_pages, ai_processed)
VALUES ('news_015', 3004, 'Company P: Short notice', datetime('now','-7 hours'), '{"mock":"row18"}', NULL, NULL, 0);

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, ai_processed, sent_to_supabase)
VALUES ('news_016', 3005, 'Company Q: Investor call', datetime('now','-6 hours'), '{"mock":"row19"}', 1, 1);

-- 21..25
INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json)
VALUES (NULL, 4001, 'Company R: Headline with special chars !@#$%^&*()', datetime('now','-5 hours'), '{"mock":"row20"}');

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, pdf_pages, ai_processed, ai_summary)
VALUES ('news_017', 4002, 'Company S: Long headline ' || substr('ABCDEFGHIJKLMNOPQRSTUVWXYZ ',1,120), datetime('now','-4 hours'), '{"mock":"row21"}', 's_long.pdf', 45, 1, 'Summary for S');

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, ai_error)
VALUES ('news_018', 4003, 'Company T: Unexpected format', datetime('now','-3 hours'), '{"mock":"row22"}', 'AI parsing crashed');

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, pdf_pages, pdf_downloaded_at)
VALUES ('news_019', 4004, 'Company U: PDF but not processed yet', datetime('now','-2 hours'), '{"mock":"row23"}', 'u_doc.pdf', 7, datetime('now','-2 hours','+5 minutes'));

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, ai_processed, ai_summary, sent_to_supabase, sent_to_supabase_at)
VALUES ('news_020', 4005, 'Company V: Completed flow', datetime('now','-90 minutes'), '{"mock":"row24"}', 1, 'Summary for V', 1, datetime('now','-80 minutes'));

-- 26..30
INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json)
VALUES ('news_021', 5001, 'Company W: Minimal filing', datetime('now','-60 minutes'), '{"mock":"row25"}');

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, pdf_pages, ai_processed, ai_error)
VALUES ('news_022', 5002, 'Company X: Big PDF but trimmed', datetime('now','-50 minutes'), '{"mock":"row26"}', 'x_big.pdf', 180, 1, NULL);

-- duplicate newsid to test UNIQUE handling (news_010 exists above) will be ignored
INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json)
VALUES ('news_010', 2007, 'Company K Duplicate rights', datetime('now','-40 minutes'), '{"mock":"row27"}');

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, ai_processed, ai_summary)
VALUES ('news_023', 5003, 'Company Y: Small update', datetime('now','-30 minutes'), '{"mock":"row28"}', 1, 'minor update');

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file)
VALUES ('news_024', 5004, 'Company Z: PDF but no pages set', datetime('now','-20 minutes'), '{"mock":"row29"}', 'z_unknown.pdf');

INSERT OR IGNORE INTO announcements(newsid, scrip_cd, headline, fetched_at, raw_json, downloaded_pdf_file, pdf_pages, ai_processed, ai_summary, sent_to_supabase)
VALUES ('news_025', 5005, 'Company AA: everything present', datetime('now','-10 minutes'), '{"mock":"row30"}', 'aa_full.pdf', 10, 1, 'All good', 1);

COMMIT;
SQL

echo "Inserted mock announcements."

echo
echo "DB path: $DB_PATH"
echo "Counts summary (sqlite3):"
sqlite3 -readonly "$DB_PATH" <<'SQL'
.mode column
-- Use non-reserved alias 'tbl_name' to avoid parsing issues
SELECT 'raw_responses' AS tbl_name, COUNT(*) AS rows FROM raw_responses
UNION ALL
SELECT 'announcements' AS tbl_name, COUNT(*) AS rows FROM announcements;
SQL

echo
echo "Quick sample (most recent 8 announcements):"
sqlite3 -readonly "$DB_PATH" <<'SQL'
.headers on
.mode column
SELECT id,newsid,scrip_cd,CASE WHEN LENGTH(COALESCE(headline,''))>100 THEN SUBSTR(headline,1,97)||'...' ELSE headline END AS headline,
COALESCE(downloaded_pdf_file,'') AS pdf_file, COALESCE(pdf_pages,'') AS pdf_pages,
COALESCE(ai_processed,0) AS ai_processed, COALESCE(sent_to_supabase,0) AS sent_to_supabase, fetched_at
FROM announcements
ORDER BY CASE WHEN fetched_at IS NOT NULL AND fetched_at != '' THEN fetched_at ELSE printf('%010d', id) END DESC
LIMIT 8;
SQL

echo
echo "Done. You can now run your analyzer script or inspect the DB with sqlite3."
