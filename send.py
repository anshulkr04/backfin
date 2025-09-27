#!/usr/bin/env python3
"""
send.py

Export announcements table and send CSV via Resend (drop-in replacement for send_csv_resend.py).

Usage:
  python send.py --to recipient@example.com
  python send.py --to recipient@example.com --db ./data/bse_raw.db --date 2025-09-21

Environment variables expected:
  RESEND_API_KEY    (your Resend API key)
  SENDER_EMAIL      (email to send from, e.g. "noreply@anshulkr.com")
  SENDER_NAME       (optional display name, e.g. "BSE Reports")

This script will read the local SQLite DB (default ./data/bse_raw.db), create a CSV of announcements (optionally filtered by date
and/or processing flags), and send it as an attachment via the Resend API.
"""

import os
import sqlite3
import csv
import io
import base64
import argparse
from datetime import datetime
import json
import sys

try:
    import resend
except Exception as e:
    print("Error: resend library not installed. Install with `pip install resend`.", file=sys.stderr)
    raise


# ---- Helpers ----

def load_env_dotenv(path=".env"):
    """If a .env file exists, load simple KEY=VALUE lines into env (non-secure simple loader)."""
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            key, val = ln.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def db_counts_and_rows(db_path, date_filter=None, where_extra=None):
    """
    Return (metrics_dict, rows_list) where rows_list is list of dicts for announcements.
    metrics_dict has keys: total_raw, total_announcements, downloaded, ai_processed, sent
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # counts
    if date_filter:
        # date_filter should be YYYY-MM-DD
        cur.execute("SELECT COUNT(*) FROM raw_responses WHERE date(fetched_at) = ?", (date_filter,))
        total_raw = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM announcements WHERE date(fetched_at) = ?", (date_filter,))
        total_ann = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM announcements WHERE date(fetched_at) = ? AND (downloaded_pdf_file IS NOT NULL AND TRIM(downloaded_pdf_file) != '')", (date_filter,))
        downloaded = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM announcements WHERE date(fetched_at) = ? AND (ai_processed = 1)", (date_filter,))
        ai_processed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM announcements WHERE date(fetched_at) = ? AND (sent_to_supabase = 1)", (date_filter,))
        sent = cur.fetchone()[0]
    else:
        cur.execute("SELECT COUNT(*) FROM raw_responses")
        total_raw = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM announcements")
        total_ann = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM announcements WHERE (downloaded_pdf_file IS NOT NULL AND TRIM(downloaded_pdf_file) != '')")
        downloaded = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM announcements WHERE (ai_processed = 1)")
        ai_processed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM announcements WHERE (sent_to_supabase = 1)")
        sent = cur.fetchone()[0]

    metrics = {
        "total_raw_responses": total_raw,
        "total_announcements": total_ann,
        "pdfs_downloaded": downloaded,
        "ai_processed": ai_processed,
        "sent_to_supabase": sent,
        "generated_at": datetime.now().isoformat()
    }

    # Now fetch rows (apply filters)
    base_sql = "SELECT id, newsid, scrip_cd, headline, downloaded_pdf_file, pdf_pages, ai_processed, sent_to_supabase, fetched_at FROM announcements"
    clauses = []
    params = []
    if date_filter:
        clauses.append("date(fetched_at) = ?")
        params.append(date_filter)
    if where_extra:
        # where_extra should be a SQL snippet like "(ai_processed = 0)"
        clauses.append(where_extra)

    if clauses:
        sql = base_sql + " WHERE " + " AND ".join(clauses) + " ORDER BY CASE WHEN fetched_at IS NOT NULL AND fetched_at != '' THEN fetched_at ELSE printf('%010d', id) END DESC"
    else:
        sql = base_sql + " ORDER BY CASE WHEN fetched_at IS NOT NULL AND fetched_at != '' THEN fetched_at ELSE printf('%010d', id) END DESC"

    cur.execute(sql, tuple(params))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return metrics, rows


def rows_to_csv_bytes(rows):
    """
    Convert list-of-dicts rows to CSV bytes and return (csv_bytes, header_fields)
    If rows is empty, produce a CSV with header only.
    """
    output = io.StringIO()
    if not rows:
        # default minimal header
        fields = ["id", "newsid", "scrip_cd", "headline", "downloaded_pdf_file", "pdf_pages", "ai_processed", "sent_to_supabase", "fetched_at"]
    else:
        # Use keys from first row but ensure consistent order
        fields = ["id", "newsid", "scrip_cd", "headline", "downloaded_pdf_file", "pdf_pages", "ai_processed", "sent_to_supabase", "fetched_at"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for r in rows:
        # ensure only fields present in header are written
        row_short = {k: r.get(k, "") for k in fields}
        writer.writerow(row_short)
    csv_text = output.getvalue()
    return csv_text.encode("utf-8"), fields


def build_html_from_metrics(metrics):
    html = f"""
    <html>
      <body>
        <h2>BSE Announcements Report</h2>
        <p>Generated at: {metrics.get('generated_at')}</p>
        <table border="1" cellpadding="6" cellspacing="0">
          <tr><th>Metric</th><th>Value</th></tr>
          <tr><td>Total raw_responses</td><td>{metrics.get('total_raw_responses')}</td></tr>
          <tr><td>Total announcements</td><td>{metrics.get('total_announcements')}</td></tr>
          <tr><td>PDFs downloaded</td><td>{metrics.get('pdfs_downloaded')}</td></tr>
          <tr><td>AI processed</td><td>{metrics.get('ai_processed')}</td></tr>
          <tr><td>Sent to Supabase</td><td>{metrics.get('sent_to_supabase')}</td></tr>
        </table>
        <p>The CSV file attached contains the announcement rows (full details).</p>
      </body>
    </html>
    """
    return html


# ---- Resend sending function ----

def send_csv_via_resend(to_email: str, csv_bytes: bytes, csv_filename: str, html_body: str, subject: str,
                        api_key: str, sender_email: str, sender_name: str = None):
    """
    Send email via resend Python client with CSV attachment (base64).
    Returns resend API response object/dict.
    """
    if not api_key:
        raise ValueError("Resend API key not provided")
    if not sender_email:
        raise ValueError("Sender email not provided")

    # configure resend client
    resend.api_key = api_key

    from_header = f"{sender_name} <{sender_email}>" if sender_name else sender_email

    # attachments: base64 string
    b64 = base64.b64encode(csv_bytes).decode("ascii")

    # Build params for resend. The exact accepted keys for attachments may vary depending
    # on the resend library version. This is one common pattern: using 'attachments' with
    # 'filename' and 'content' (base64). If your resend SDK expects a different key,
    # change accordingly (e.g., 'data' or 'content' -> 'content').
    params = {
        "from": from_header,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
        "attachments": [
            {
                "filename": csv_filename,
                "content": b64,
                "type": "text/csv",
                "disposition": "attachment"
            }
        ]
    }

    # send
    try:
        resp = resend.Emails.send(params)
        return resp
    except Exception as e:
        # rethrow or return structured error
        raise RuntimeError(f"Failed to send email via Resend: {e}")


# ---- CLI entrypoint ----

def main():
    parser = argparse.ArgumentParser(description="Export announcements table and send CSV via Resend")
    parser.add_argument("--to", "-m", required=True, help="Recipient email address")
    parser.add_argument("--db", default="./data/bse_raw.db", help="Path to bse_raw.db")
    parser.add_argument("--date", help="Optional date filter (YYYY-MM-DD) to restrict rows and metrics")
    parser.add_argument("--only-not-down", action="store_true", help="Include only rows where downloaded_pdf_file is missing")
    parser.add_argument("--only-not-proc", action="store_true", help="Include only rows where ai_processed is 0 or NULL")
    parser.add_argument("--only-not-sent", action="store_true", help="Include only rows where sent_to_supabase is 0 or NULL")
    parser.add_argument("--subject", help="Email subject", default=None)
    parser.add_argument("--envfile", help="Optional .env file to load before running", default=".env")
    args = parser.parse_args()

    # load env if present
    load_env_dotenv(args.envfile)

    RESEND_API_KEY = os.getenv("RESEND_API_KEY") or os.getenv("RESEND_API_KEY".upper())
    SENDER_EMAIL = os.getenv("SENDER_EMAIL") or os.getenv("SMTP_FROM") or os.getenv("SMTP_FROM".upper())
    SENDER_NAME = os.getenv("SENDER_NAME", None)

    if not RESEND_API_KEY:
        print("Error: RESEND_API_KEY not set in environment or .env", file=sys.stderr)
        sys.exit(2)
    if not SENDER_EMAIL:
        print("Error: SENDER_EMAIL (sender address) not set in environment or .env", file=sys.stderr)
        sys.exit(2)

    # Determine additional WHERE filter
    where_extra = None
    # If multiple of only-not-* flags are set, combine them with AND
    extra_clauses = []
    if args.only_not_down:
        extra_clauses.append("(downloaded_pdf_file IS NULL OR TRIM(downloaded_pdf_file) = '')")
    if args.only_not_proc:
        extra_clauses.append("(ai_processed = 0 OR ai_processed IS NULL)")
    if args.only_not_sent:
        extra_clauses.append("(sent_to_supabase = 0 OR sent_to_supabase IS NULL)")
    if extra_clauses:
        where_extra = " AND ".join(extra_clauses)

    # get metrics and rows
    metrics, rows = db_counts_and_rows(args.db, date_filter=args.date, where_extra=where_extra)

    # build CSV
    csv_bytes, fields = rows_to_csv_bytes(rows)

    # build HTML body
    html_body = build_html_from_metrics(metrics)

    # subject
    subj = args.subject or f"BSE Announcements CSV — {metrics.get('total_announcements')} announcements"

    # send email
    filename = f"announcements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    try:
        resp = send_csv_via_resend(
            to_email=args.to,
            csv_bytes=csv_bytes,
            csv_filename=filename,
            html_body=html_body,
            subject=subj,
            api_key=RESEND_API_KEY,
            sender_email=SENDER_EMAIL,
            sender_name=SENDER_NAME
        )
        print("Email send response:")
        try:
            # try to pretty-print if it's JSON-like
            print(json.dumps(resp, indent=2, default=str))
        except Exception:
            print(resp)
        print("Done.")
    except Exception as e:
        print("Failed to send email:", e, file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
