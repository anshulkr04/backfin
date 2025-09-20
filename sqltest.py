#!/usr/bin/env python3
"""
sqlite_smoke_test.py

Creates a sqlite DB file, inserts random rows, runs basic queries, and reports success/failure.
"""

import sqlite3
import argparse
import os
import sys
import secrets
import string
from datetime import datetime

def random_string(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def connect_db(path):
    try:
        conn = sqlite3.connect(path, timeout=5)
        return conn
    except Exception as e:
        print(f"[ERROR] Could not connect to '{path}': {e}")
        return None

def create_table(conn):
    sql = """
    CREATE TABLE IF NOT EXISTS smoke_test (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rnd_text TEXT NOT NULL,
        rnd_int INTEGER NOT NULL,
        created_at TEXT NOT NULL
    );
    """
    conn.execute(sql)
    conn.commit()

def insert_random_rows(conn, n=10):
    insert_sql = "INSERT INTO smoke_test (rnd_text, rnd_int, created_at) VALUES (?, ?, ?)"
    cur = conn.cursor()
    rows = []
    for _ in range(n):
        txt = random_string(8)
        val = secrets.randbelow(10000)
        ts = datetime.utcnow().isoformat() + "Z"
        cur.execute(insert_sql, (txt, val, ts))
        rows.append((txt, val, ts))
    conn.commit()
    return rows

def run_select_test(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM smoke_test")
    count = cur.fetchone()[0]
    # fetch a sample row
    cur.execute("SELECT id, rnd_text, rnd_int, created_at FROM smoke_test ORDER BY id DESC LIMIT 1")
    sample = cur.fetchone()
    return count, sample

def run_update_test(conn, row_id):
    cur = conn.cursor()
    new_text = "UPDATED_" + random_string(6)
    cur.execute("UPDATE smoke_test SET rnd_text = ? WHERE id = ?", (new_text, row_id))
    conn.commit()
    cur.execute("SELECT rnd_text FROM smoke_test WHERE id = ?", (row_id,))
    updated = cur.fetchone()
    return new_text, (updated[0] if updated else None)

def run_delete_test(conn, row_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM smoke_test WHERE id = ?", (row_id,))
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM smoke_test WHERE id = ?", (row_id,))
    left = cur.fetchone()[0]
    return left == 0

def main(args):
    db_path = args.db
    db_exists_before = os.path.exists(db_path)
    print(f"[INFO] Using DB file: {db_path} (exists already: {db_exists_before})")

    conn = connect_db(db_path)
    if conn is None:
        print("[FAIL] Could not open sqlite database.")
        return 2

    try:
        create_table(conn)
        inserted = insert_random_rows(conn, n=args.rows)
        print(f"[INFO] Inserted {len(inserted)} rows.")

        count, sample = run_select_test(conn)
        print(f"[INFO] Total rows now in table: {count}")
        if sample:
            print(f"[INFO] Sample latest row: id={sample[0]}, rnd_text={sample[1]}, rnd_int={sample[2]}, created_at={sample[3]}")
        else:
            print("[WARN] No sample row retrieved after insert.")

        # Update test
        if sample:
            row_id = sample[0]
            expect_text, observed_text = run_update_test(conn, row_id)
            if observed_text == expect_text:
                print(f"[INFO] UPDATE test passed for id={row_id}")
            else:
                print(f"[FAIL] UPDATE test mismatch (expected '{expect_text}', got '{observed_text}')")
                return 3

            # Delete test
            deleted_ok = run_delete_test(conn, row_id)
            if deleted_ok:
                print(f"[INFO] DELETE test passed for id={row_id}")
            else:
                print(f"[FAIL] DELETE test failed for id={row_id}")
                return 4
        else:
            print("[WARN] Skipping UPDATE/DELETE tests because no sample row.")
        
        # final check: ensure DB file exists and is writable
        if os.path.exists(db_path):
            try:
                with open(db_path, "rb"):
                    pass
                print(f"[SUCCESS] SQLite appears to be working. DB file present: {db_path}")
                return 0
            except Exception as e:
                print(f"[WARN] DB file exists but could not be opened for read: {e}")
                return 5
        else:
            print("[FAIL] DB file does not exist after operations.")
            return 6

    except Exception as e:
        print(f"[EXCEPTION] Error during tests: {e}")
        return 7
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQLite smoke test: create DB, insert random rows, run queries.")
    parser.add_argument("--db", "-d", default="sqlite_smoke_test.db", help="Path to sqlite db file to create/use.")
    parser.add_argument("--rows", "-n", type=int, default=10, help="Number of random rows to insert.")
    args = parser.parse_args()

    exit_code = main(args)
    sys.exit(exit_code)
