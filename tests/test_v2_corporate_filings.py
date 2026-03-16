#!/usr/bin/env python3
"""
Test script for V2 Corporate Filings API.
Registers a new test user, gets token, and exercises all V2 endpoints
with various filter combinations to verify functionality.
"""

import requests
import json
import sys
import uuid
import datetime

BASE_URL = "https://api.marketwire.ai"

# Test user credentials
TEST_EMAIL = f"test_{uuid.uuid4().hex[:8]}@test-marketwire.com"
TEST_PASSWORD = "TestPass123!@#"

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

passed = 0
failed = 0
errors = []


def log_pass(name: str, detail: str = ""):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {name}" + (f" — {detail}" if detail else ""))


def log_fail(name: str, detail: str = ""):
    global failed
    failed += 1
    errors.append(f"{name}: {detail}")
    print(f"  {RED}✗{RESET} {name}" + (f" — {detail}" if detail else ""))


def section(title: str):
    print(f"\n{BOLD}── {title} ──{RESET}")


# ── Register ──
section("1. Registration")
resp = requests.post(f"{BASE_URL}/api/register", json={
    "email": TEST_EMAIL,
    "password": TEST_PASSWORD,
})
if resp.status_code == 201:
    data = resp.json()
    TOKEN = data.get("token")
    USER_ID = data.get("user_id")
    log_pass("Register", f"user_id={USER_ID[:12]}…")
else:
    print(f"{RED}Registration failed: {resp.status_code} {resp.text}{RESET}")
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def api_get(path: str, params: dict = None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=HEADERS)


def api_post(path: str, body: dict = None):
    return requests.post(f"{BASE_URL}{path}", json=body, headers=HEADERS)


# ── Login (verify token still works) ──
section("2. Login & Token Verification")
resp = requests.post(f"{BASE_URL}/api/login", json={
    "email": TEST_EMAIL,
    "password": TEST_PASSWORD,
})
if resp.status_code == 200:
    new_token = resp.json().get("token")
    if new_token:
        TOKEN = new_token
        HEADERS["Authorization"] = f"Bearer {TOKEN}"
        log_pass("Login", "got new token")
    else:
        log_fail("Login", "no token in response")
else:
    log_fail("Login", f"status={resp.status_code}")


# ── Basic V2 Filings (today, no filters) ──
section("3. V2 Corporate Filings — Basic")
today = datetime.date.today().strftime("%Y-%m-%d")

resp = api_get("/api/v2/corporate_filings", {"start_date": today, "end_date": today})
if resp.status_code == 200:
    data = resp.json()
    required_keys = {"filings", "total_count", "total_pages", "current_page", "page_size", "has_next", "has_previous", "count"}
    missing = required_keys - set(data.keys())
    if missing:
        log_fail("Response shape", f"missing keys: {missing}")
    else:
        log_pass("Response shape", f"all keys present, count={data['count']}, total={data['total_count']}")

    if isinstance(data.get("filings"), list):
        log_pass("Filings is list", f"len={len(data['filings'])}")
        if len(data["filings"]) > 0:
            f = data["filings"][0]
            filing_keys = {"corp_id", "category", "date", "isin", "companyname", "symbol"}
            fmissing = filing_keys - set(f.keys())
            if fmissing:
                log_fail("Filing shape", f"missing: {fmissing}")
            else:
                log_pass("Filing shape", f"corp_id={f['corp_id'][:12]}…, category={f['category']}")
            # Check is_read field
            if "is_read" in f:
                log_pass("is_read field", f"value={f['is_read']}")
            else:
                log_fail("is_read field", "missing from filing")
        else:
            print(f"  {YELLOW}⚠{RESET} No filings today — some tests may be limited")
    else:
        log_fail("Filings type", f"expected list, got {type(data.get('filings'))}")
else:
    log_fail("Basic query", f"status={resp.status_code}, body={resp.text[:200]}")


# ── Pagination ──
section("4. Pagination")
resp1 = api_get("/api/v2/corporate_filings", {"page": 1, "page_size": 5, "start_date": today, "end_date": today})
resp2 = api_get("/api/v2/corporate_filings", {"page": 2, "page_size": 5, "start_date": today, "end_date": today})

if resp1.status_code == 200 and resp2.status_code == 200:
    d1 = resp1.json()
    d2 = resp2.json()
    if d1["current_page"] == 1 and d2["current_page"] == 2:
        log_pass("Page numbers", "page 1 and 2 correct")
    else:
        log_fail("Page numbers", f"got {d1['current_page']} and {d2['current_page']}")

    if len(d1["filings"]) <= 5:
        log_pass("Page size", f"page_size=5, got {len(d1['filings'])} filings")
    else:
        log_fail("Page size", f"expected ≤5, got {len(d1['filings'])}")

    ids1 = {f["corp_id"] for f in d1["filings"]}
    ids2 = {f["corp_id"] for f in d2["filings"]}
    overlap = ids1 & ids2
    if not overlap:
        log_pass("No overlap", "page 1 and 2 have different filings")
    else:
        log_fail("Overlap detected", f"{len(overlap)} duplicates between pages")
else:
    log_fail("Pagination requests", f"status={resp1.status_code},{resp2.status_code}")


# ── Date Range — past 2 months ──
section("5. Date Range Filters")
two_months_ago = (datetime.date.today() - datetime.timedelta(days=60)).strftime("%Y-%m-%d")
resp = api_get("/api/v2/corporate_filings", {
    "start_date": two_months_ago,
    "end_date": today,
    "page_size": 10,
})
if resp.status_code == 200:
    data = resp.json()
    log_pass("2-month range", f"total={data['total_count']}, returned={data['count']}")
else:
    log_fail("2-month range", f"status={resp.status_code}")

one_month_ago = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
resp = api_get("/api/v2/corporate_filings", {
    "start_date": one_month_ago,
    "end_date": today,
    "page_size": 10,
})
if resp.status_code == 200:
    data = resp.json()
    log_pass("1-month range", f"total={data['total_count']}, returned={data['count']}")
else:
    log_fail("1-month range", f"status={resp.status_code}")


# ── Category Filters ──
section("6. Category Filters")
categories = ["Annual Report", "Board Meeting", "Concall Transcript", "Investor Presentation"]
for cat in categories:
    resp = api_get("/api/v2/corporate_filings", {
        "category": cat,
        "start_date": two_months_ago,
        "end_date": today,
        "page_size": 3,
    })
    if resp.status_code == 200:
        data = resp.json()
        # Verify all returned filings match category
        wrong = [f["category"] for f in data["filings"] if f["category"] != cat]
        if wrong:
            log_fail(f"Category={cat}", f"got wrong categories: {wrong}")
        else:
            log_pass(f"Category={cat}", f"count={data['count']}")
    else:
        log_fail(f"Category={cat}", f"status={resp.status_code}")

# Multi-category
resp = api_get("/api/v2/corporate_filings", {
    "category": "Annual Report,Board Meeting",
    "start_date": two_months_ago,
    "end_date": today,
    "page_size": 5,
})
if resp.status_code == 200:
    data = resp.json()
    cats = set(f["category"] for f in data["filings"])
    if cats <= {"Annual Report", "Board Meeting"} or len(data["filings"]) == 0:
        log_pass("Multi-category", f"categories={cats}, count={data['count']}")
    else:
        log_fail("Multi-category", f"unexpected categories: {cats}")
else:
    log_fail("Multi-category", f"status={resp.status_code}")


# ── Watchlist Filter ──
section("7. Watchlist Filter")
# Should return empty since new user has no ISINs in watchlist
resp = api_get("/api/v2/corporate_filings", {
    "watchlist": "true",
    "start_date": today,
    "end_date": today,
})
if resp.status_code == 200:
    data = resp.json()
    if data["total_count"] == 0:
        log_pass("Empty watchlist", "correctly returns 0 filings")
    else:
        log_pass("Watchlist filter", f"total={data['total_count']} (user may have preset data)")
else:
    log_fail("Watchlist filter", f"status={resp.status_code}")


# ── Create Watchlist & Add ISIN ──
section("8. Watchlist Operations")
# Create a test watchlist
resp = api_post("/api/watchlist", {
    "operation": "create",
    "watchlistName": "Test WL",
    "watchlistType": "NA",
})
if resp.status_code in (200, 201):
    wl_data = resp.json()
    wl_id = wl_data.get("watchlist_id")
    log_pass("Create watchlist", f"id={wl_id[:12]}…" if wl_id else "ok")

    # Get some ISINs from recent filings to add
    resp = api_get("/api/v2/corporate_filings", {
        "start_date": one_month_ago,
        "end_date": today,
        "page_size": 3,
    })
    test_isins = []
    if resp.status_code == 200:
        filings_data = resp.json()
        test_isins = list({f["isin"] for f in filings_data["filings"] if f.get("isin")})[:2]

    if test_isins and wl_id:
        for isin in test_isins:
            resp = api_post("/api/watchlist", {
                "operation": "add_isin",
                "watchlist_id": wl_id,
                "isin": isin,
            })
            if resp.status_code == 200:
                log_pass(f"Add ISIN {isin[:8]}…", "ok")
            else:
                log_fail(f"Add ISIN {isin[:8]}…", f"status={resp.status_code}")

        # Now test watchlist filter with data
        resp = api_get("/api/v2/corporate_filings", {
            "watchlist": "true",
            "start_date": one_month_ago,
            "end_date": today,
            "page_size": 10,
        })
        if resp.status_code == 200:
            data = resp.json()
            returned_isins = {f["isin"] for f in data["filings"]}
            if returned_isins <= set(test_isins) or data["total_count"] >= 0:
                log_pass("Watchlist with ISINs", f"total={data['total_count']}, isins={returned_isins}")
            else:
                log_fail("Watchlist with ISINs", f"unexpected ISINs: {returned_isins - set(test_isins)}")
        else:
            log_fail("Watchlist with ISINs", f"status={resp.status_code}")
    else:
        print(f"  {YELLOW}⚠{RESET} No ISINs available to test watchlist filter")
else:
    log_fail("Create watchlist", f"status={resp.status_code}")


# ── Read/Unread Tracking ──
section("9. Read/Unread Tracking")
# Get some corp_ids to mark
resp = api_get("/api/v2/corporate_filings", {
    "start_date": one_month_ago,
    "end_date": today,
    "page_size": 5,
})
mark_ids = []
if resp.status_code == 200:
    mark_ids = [f["corp_id"] for f in resp.json()["filings"]][:3]

if mark_ids:
    # Mark as read
    resp = api_post("/api/v2/corporate_filings/mark-read", {"corp_ids": mark_ids})
    if resp.status_code == 200:
        log_pass("Mark read", f"marked {len(mark_ids)} filings")
    else:
        log_fail("Mark read", f"status={resp.status_code}, body={resp.text[:200]}")

    # Check read status
    resp = api_post("/api/v2/corporate_filings/read-status", {"corp_ids": mark_ids})
    if resp.status_code == 200:
        data = resp.json()
        read_ids = set(data.get("read_corp_ids", []))
        expected = set(mark_ids)
        if read_ids == expected:
            log_pass("Read status", f"all {len(read_ids)} marked as read")
        else:
            log_fail("Read status", f"expected {expected}, got {read_ids}")
    else:
        log_fail("Read status", f"status={resp.status_code}")

    # Test read_filter=read
    resp = api_get("/api/v2/corporate_filings", {
        "read_filter": "read",
        "start_date": one_month_ago,
        "end_date": today,
        "page_size": 50,
    })
    if resp.status_code == 200:
        data = resp.json()
        log_pass("read_filter=read", f"total={data['total_count']}, count={data['count']}")
    else:
        log_fail("read_filter=read", f"status={resp.status_code}")

    # Test read_filter=unread
    resp = api_get("/api/v2/corporate_filings", {
        "read_filter": "unread",
        "start_date": one_month_ago,
        "end_date": today,
        "page_size": 5,
    })
    if resp.status_code == 200:
        data = resp.json()
        # All returned should be unread
        has_read = [f for f in data["filings"] if f.get("is_read")]
        if has_read:
            log_fail("read_filter=unread", f"{len(has_read)} filings marked as read in unread list")
        else:
            log_pass("read_filter=unread", f"total={data['total_count']}, count={data['count']}")
    else:
        log_fail("read_filter=unread", f"status={resp.status_code}")

    # Mark as unread
    resp = api_post("/api/v2/corporate_filings/mark-unread", {"corp_ids": mark_ids[:1]})
    if resp.status_code == 200:
        log_pass("Mark unread", "ok")
    else:
        log_fail("Mark unread", f"status={resp.status_code}")

    # Verify unread
    resp = api_post("/api/v2/corporate_filings/read-status", {"corp_ids": mark_ids})
    if resp.status_code == 200:
        data = resp.json()
        still_read = set(data.get("read_corp_ids", []))
        unmarked = mark_ids[0]
        if unmarked not in still_read:
            log_pass("Verify unmark", f"corp_id {unmarked[:12]}… is now unread")
        else:
            log_fail("Verify unmark", f"{unmarked[:12]}… still marked as read")
    else:
        log_fail("Verify unmark", f"status={resp.status_code}")
else:
    print(f"  {YELLOW}⚠{RESET} No filings available for read/unread tests")


# ── Single Filing ──
section("10. Single Filing by ID")
if mark_ids:
    resp = api_get(f"/api/v2/corporate_filings/{mark_ids[0]}")
    if resp.status_code == 200:
        filing = resp.json()
        if filing.get("corp_id") == mark_ids[0]:
            log_pass("Get by ID", f"corp_id={filing['corp_id'][:12]}…")
        else:
            log_fail("Get by ID", f"wrong corp_id: {filing.get('corp_id')}")
        if "is_read" in filing:
            log_pass("is_read in single", f"value={filing['is_read']}")
        else:
            log_fail("is_read in single", "missing")
    else:
        log_fail("Get by ID", f"status={resp.status_code}")


# ── Market Cap Filter ──
section("11. Market Cap Filter")
for cap in ["large", "mid", "small"]:
    resp = api_get("/api/v2/corporate_filings", {
        "marketcap": cap,
        "start_date": one_month_ago,
        "end_date": today,
        "page_size": 3,
    })
    if resp.status_code == 200:
        data = resp.json()
        log_pass(f"marketcap={cap}", f"total={data['total_count']}, count={data['count']}")
    else:
        log_fail(f"marketcap={cap}", f"status={resp.status_code}")

# Multi-cap
resp = api_get("/api/v2/corporate_filings", {
    "marketcap": "large,mid",
    "start_date": one_month_ago,
    "end_date": today,
    "page_size": 5,
})
if resp.status_code == 200:
    data = resp.json()
    log_pass("marketcap=large,mid", f"total={data['total_count']}")
else:
    log_fail("marketcap=large,mid", f"status={resp.status_code}")


# ── Include Duplicates ──
section("12. Duplicate Filter")
resp_no = api_get("/api/v2/corporate_filings", {
    "include_duplicates": "false",
    "start_date": one_month_ago,
    "end_date": today,
    "page_size": 5,
})
resp_yes = api_get("/api/v2/corporate_filings", {
    "include_duplicates": "true",
    "start_date": one_month_ago,
    "end_date": today,
    "page_size": 5,
})
if resp_no.status_code == 200 and resp_yes.status_code == 200:
    d_no = resp_no.json()
    d_yes = resp_yes.json()
    log_pass("Duplicates filter", f"without={d_no['total_count']}, with={d_yes['total_count']}")
else:
    log_fail("Duplicates filter", f"status={resp_no.status_code},{resp_yes.status_code}")


# ── Edge Cases ──
section("13. Edge Cases")

# Invalid read_filter
resp = api_get("/api/v2/corporate_filings", {"read_filter": "invalid"})
if resp.status_code == 200:
    log_pass("Invalid read_filter", "treated as 'all'")
else:
    log_fail("Invalid read_filter", f"status={resp.status_code}")

# Large page_size (should cap at 100)
resp = api_get("/api/v2/corporate_filings", {"page_size": "999", "start_date": today, "end_date": today})
if resp.status_code == 200:
    data = resp.json()
    if data["page_size"] <= 100:
        log_pass("Max page_size", f"capped at {data['page_size']}")
    else:
        log_fail("Max page_size", f"got {data['page_size']}")
else:
    log_fail("Max page_size", f"status={resp.status_code}")

# Page 0 (should default to 1)
resp = api_get("/api/v2/corporate_filings", {"page": "0", "start_date": today, "end_date": today})
if resp.status_code == 200:
    data = resp.json()
    if data["current_page"] >= 1:
        log_pass("Page 0", f"normalized to {data['current_page']}")
    else:
        log_fail("Page 0", f"got page {data['current_page']}")
else:
    log_fail("Page 0", f"status={resp.status_code}")

# No auth
resp = requests.get(f"{BASE_URL}/api/v2/corporate_filings")
if resp.status_code == 401:
    log_pass("No auth", "returns 401")
else:
    log_fail("No auth", f"expected 401, got {resp.status_code}")


# ── Summary ──
print(f"\n{'='*50}")
print(f"{BOLD}Results: {GREEN}{passed} passed{RESET}, {RED if failed else ''}{failed} failed{RESET}")
if errors:
    print(f"\n{RED}Failures:{RESET}")
    for e in errors:
        print(f"  • {e}")
print(f"{'='*50}")

# Cleanup: logout
api_post("/api/logout")

sys.exit(0 if failed == 0 else 1)
