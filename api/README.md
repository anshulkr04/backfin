# Financial Backend API

A comprehensive backend API for financial data management with support for user authentication, watchlists, corporate filings, and real-time notifications via WebSockets.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Setup and Installation](#setup-and-installation)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
  - [Health Check](#health-check)
  - [User Management](#user-management)
  - [Watchlists](#watchlists)
  - [Corporate Filings](#corporate-filings)
  - [Company Search](#company-search)
  - [Stock Price Data](#stock-price-data)
  - [Announcements](#announcements)
  - [Admin Endpoints](#admin-endpoints)
  - [System Status](#system-status)
- [WebSocket Integration](#websocket-integration)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## Overview

This Financial Backend API provides a robust platform for managing financial data, user accounts, and watchlists. It uses Flask as the web framework, Supabase for database operations, and Socket.IO for real-time notifications. The server supports RESTful API endpoints with proper authentication and CORS handling.

## Features

- **Custom Authentication System**: Secure user registration and authentication
- **Watchlist Management**: Create and manage stock watchlists with ISINs and categories
- **Corporate Filings**: Access corporate announcements and filings with advanced filtering
- **Real-time Notifications**: Receive new announcements via WebSockets
- **Company Search**: Search for company information by name, code, or ISIN
- **CORS Support**: Cross-Origin Resource Sharing enabled for all endpoints
- **Logging**: Comprehensive logging for debugging and monitoring
- **Error Handling**: Consistent error responses with appropriate status codes
- **Background Scrapers**: Automated data collection from BSE and NSE
- **Announcement Management**: Save and broadcast financial announcements

## Setup and Installation

### Prerequisites

- Python 3.7+
- PostgreSQL database (via Supabase)
- Required Python packages (listed in requirements.txt)

### Environment Variables

Create a `.env` file with the following variables:

```
DEBUG_MODE=true
PORT=5001
SUPABASE_URL2=your_supabase_url
SUPABASE_KEY2=your_supabase_key
PASSWORD_SALT=your_password_salt
```

### Installation Steps

1. Clone the repository
```bash
git clone https://github.com/your-repository/financial-backend.git
cd financial-backend
```

2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Run the server
```bash
python liveserver.py
```

The server will start on http://fin.anshulkr.com by default.

## Authentication

The API uses a custom token-based authentication system. All protected endpoints require an `Authorization` header with a Bearer token.

### Authentication Flow

1. **Register** a new user to receive an access token
2. Include the token in the `Authorization` header for subsequent requests:
   ```
   Authorization: Bearer YOUR_ACCESS_TOKEN
   ```
3. If the token becomes invalid, **login** again to receive a new token

## API Endpoints

### Health Check

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/health` or `/api/health` | GET | Check server health and status | No |

#### Response Example
```json
{
  "status": "ok",
  "timestamp": "2025-05-20T12:00:00.000Z",
  "server": "Financial Backend API (Custom Auth)",
  "supabase_connected": true,
  "debug_mode": true,
  "environment": {
    "supabase_url_set": true,
    "supabase_key_set": true
  }
}
```

### User Management

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/register` | POST | Register a new user | No |
| `/api/login` | POST | Login and receive token | No |
| `/api/logout` | POST | Invalidate current token | Yes |
| `/api/user` | GET | Get current user profile | Yes |
| `/api/update_user` | PUT | Update user information | Yes |
| `/api/upgrade_account` | POST | Upgrade account type | Yes |

#### Register User Example
```bash
curl -X POST https://fin.anshulkr.com/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "secure_password",
    "account_type": "free"
  }'
```

#### Response
```json
{
  "message": "User registered successfully!",
  "user_id": "f8a92dc1-5e42-4b67-b4d9-e8a317f8e2a3",
  "token": "your_access_token"
}
```

#### Login Example
```bash
curl -X POST https://fin.anshulkr.com/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "secure_password"
  }'
```

#### Get User Profile Example
```bash
curl -X GET https://fin.anshulkr.com/api/user \
  -H "Authorization: Bearer your_access_token"
```

# Get Announcement count
```bash
curl -X GET "https://fin.anshulkr.com/api/get_count?start_date=2025-11-12&end_date=2025-11-12"
```
#### Response
```json
{"end_date":"2025-11-12","grand_total":2513,"start_date":"2025-11-12","total_counts":{"Agreements/MoUs":28,"Annual Report":0,"Anti-dumping Duty":0,"Bonus/Stock Split":1,"Buyback":1,"Change in Address":1,"Change in KMP":7,"Change in MOA":1,"Clarifications/Confirmations":20,"Closure of Factory":0,"Concall Transcript":59,"Consolidation of Shares":0,"Credit Rating":8,"DRHP":0,"Debt & Financing":8,"Debt Reduction":2,"Delisting":1,"Demerger":2,"Demise of KMP":2,"Disruption of Operations":1,"Divestitures":7,"Expansion":11,"Financial Results":1023,"Fundraise - Preferential Issue":21,"Fundraise - QIP":0,"Fundraise - Rights Issue":7,"Global Pharma Regulation":1,"Incorporation/Cessation of Subsidiary":4,"Increase in Share Capital":18,"Insolvency and Bankruptcy":4,"Interest Rates Updates":0,"Investor Presentation":163,"Investor/Analyst Meet":112,"Joint Ventures":7,"Litigation & Notices":12,"Mergers/Acquisitions":37,"Name Change":0,"New Order":6,"New Product":5,"One Time Settlement (OTS)":0,"Open Offer":2,"Operational Update":145,"PLI Scheme":0,"Procedural/Administrative":781,"Reduction in Share Capital":0,"Regulatory Approvals/Orders":4,"Trading Suspension":0,"USFDA":1}}
```

### Watchlists

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/watchlist` | GET | Get all user watchlists | Yes |
| `/api/watchlist` | POST | Create watchlist or add ISIN | Yes |
| `/api/watchlist/bulk_add` | POST | Add multiple ISINs to watchlist | Yes |
| `/api/watchlist/<watchlist_id>/isin/<isin>` | DELETE | Remove ISIN from watchlist | Yes |
| `/api/watchlist/<watchlist_id>` | DELETE | Delete a watchlist | Yes |
| `/api/watchlist/<watchlist_id>/clear` | POST | Clear all ISINs from watchlist | Yes |

#### Get All Watchlists Example
```bash
curl -X GET https://fin.anshulkr.com/api/watchlist \
  -H "Authorization: Bearer your_access_token"
```

#### Response
```json
{
  "watchlists": [
    {
      "_id": "550e8400-e29b-41d4-a716-446655440000",
      "watchlistName": "Tech Stocks",
      "category": "Technology",
      "isin": ["US0378331005", "US5949181045"]
    },
    {
      "_id": "550e8400-e29b-41d4-a716-446655440001",
      "watchlistName": "Financial Stocks",
      "category": "Finance",
      "isin": ["US1844991018", "US0846707026"]
    }
  ]
}
```

#### Create New Watchlist Example
```bash
curl -X POST https://fin.anshulkr.com/api/watchlist \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_access_token" \
  -d '{
    "operation": "create",
    "watchlistName": "Tech Portfolio"
    "watchlistType": "DS"
  }'
```
#### watchlistType could be only:
* "DS" : "Daily Summary"(Email at 9PM)
* "SM" : "Smart Alerts"(Whatsapp instantly)
* "NA" : "No Alerts"

#### Add ISIN with Single Category Example
```bash
curl -X POST https://fin.anshulkr.com/api/watchlist \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_access_token" \
  -d '{
    "operation": "add_isin",
    "watchlist_id": "550e8400-e29b-41d4-a716-446655440000",
    "isin": "US0378331005",
    "category": "Technology"
  }'
```

#### Add ISIN with Multiple Categories Example
```bash
curl -X POST https://fin.anshulkr.com/api/watchlist \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_access_token" \
  -d '{
    "operation": "add_isin",
    "watchlist_id": "550e8400-e29b-41d4-a716-446655440000",
    "isin": "US0378331005",
    "categories": ["Technology", "Healthcare", "Finance"]
  }'
```

#### Add Multiple Categories Without ISIN Example
```bash
curl -X POST https://fin.anshulkr.com/api/watchlist \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_access_token" \
  -d '{
    "operation": "add_isin",
    "watchlist_id": "550e8400-e29b-41d4-a716-446655440000",
    "categories": ["Technology", "Healthcare", "Finance", "Real Estate"]
  }'
```

#### Multiple Categories Response Example
```json
{
  "message": "Items added to watchlist successfully!",
  "watchlist_id": "550e8400-e29b-41d4-a716-446655440000",
  "isin": "US0378331005",
  "categories": ["Technology", "Healthcare", "Finance"]
}
```

**Category Features:**
- **Single Category**: Use `"category": "Technology"` for backward compatibility
- **Multiple Categories**: Use `"categories": ["Technology", "Healthcare", "Finance"]` for adding multiple categories at once
- **Duplicate Prevention**: The system automatically removes duplicate categories and skips existing ones
- **Batch Processing**: All categories are added in a single database request for efficiency
- **Category Only**: You can add categories without an ISIN by omitting the `isin` field

# Bulk Add ISINs to Watchlist

This API endpoint allows you to add multiple ISINs to a watchlist in a single operation, while maintaining the database structure where each ISIN is stored in a separate row.

## Endpoint Details

- **URL**: `/api/watchlist/bulk_add`
- **Method**: `POST`
- **Authentication Required**: Yes (Bearer Token)

## Request Body

```json
{
  "watchlist_id": "550e8400-e29b-41d4-a716-446655440000",
  "isins": [
    "US0378331005",
    "US5949181045",
    "US0231351067",
    "US02079K1079"
  ],
  "category": "Technology"  // Optional
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `watchlist_id` | String | Yes | The UUID of the watchlist to add ISINs to |
| `isins` | Array | Yes | An array of ISIN codes (12-character alphanumeric) |
| `category` | Array | No | Optional category to set for the watchlist |

## Response

### Success Response (200 OK)

```json
{
  "message": "Added 3 ISINs successfully, 1 duplicates skipped",
  "successful": [
    "US5949181045",
    "US0231351067",
    "US02079K1079"
  ],
  "duplicates": [
    "US0378331005"
  ],
  "failed": [],
  "watchlist": {
    "_id": "550e8400-e29b-41d4-a716-446655440000",
    "watchlistName": "Tech Portfolio",
    "category": "Technology",
    "isin": [
      "US0378331005",
      "US5949181045",
      "US0231351067",
      "US02079K1079"
    ]
  }
}
```

### Error Response

#### Invalid Request (400 Bad Request)

```json
{
  "message": "isins must be an array"
}
```

#### Watchlist Not Found (404 Not Found)

```json
{
  "message": "Watchlist not found or unauthorized"
}
```

#### Server Error (500 Internal Server Error)

```json
{
  "message": "Failed to add ISINs: [error details]"
}
```

## Examples

### cURL Example

```bash
curl -X POST https://fin.anshulkr.com/api/watchlist/bulk_add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_access_token" \
  -d '{
    "watchlist_id": "550e8400-e29b-41d4-a716-446655440000",
    "isins": [
      "US0378331005",
      "US5949181045",
      "US0231351067",
      "US02079K1079"
    ],
    "category": ["Technology" , "Pharma"]
  }'
```

## Implementation Details

1. Each ISIN is validated for format (12-character alphanumeric)
2. Duplicate ISINs (already in the watchlist) are skipped
3. Each ISIN is inserted as a separate row in the `watchlistdata` table
4. Multiple categories are supported and processed in batch
5. Duplicate categories are automatically filtered out
6. Categories and ISINs are inserted in a single database transaction for efficiency
7. The response includes detailed information about successful, duplicate, and failed ISINs
8. The response format matches the GET watchlist endpoint (categories as array)

### Corporate Filings

The Corporate Filings API provides access to corporate announcements and filings with advanced filtering capabilities, improved date handling, and robust error handling with fallback mechanisms.

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/corporate_filings` | GET | Get corporate filings with advanced filters | Yes |
| `/api/corporate_filings/<corp_id>` | GET | Get specific filing by ID | No |
| `/api/test_corporate_filings` | GET | Get test corporate filings | No |

#### Features

- **Advanced Date Filtering**: Proper ISO format date handling with time zone support
- **Multiple Filter Options**: Filter by category, symbol, ISIN, and date ranges
- **Procedural Filtering**: Option to exclude procedural/administrative filings
- **Fallback Mechanisms**: Multiple levels of fallback when primary queries fail
- **Test Data Support**: Automatic fallback to test data ensures API availability
- **Enhanced Error Handling**: Comprehensive error handling with detailed logging

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | String | No | Start date in YYYY-MM-DD format |
| `end_date` | String | No | End date in YYYY-MM-DD format |
| `category` | String | No | Filter by filing category |
| `symbol` | String | No | Filter by company symbol |
| `isin` | String | No | Filter by ISIN code |

#### Date Handling

The API automatically handles date conversion:
- **Input**: YYYY-MM-DD format (e.g., "2025-01-15")
- **Start Date**: Converted to beginning of day (00:00:00)
- **End Date**: Converted to end of day (23:59:59)
- **Storage**: ISO format with timezone support

#### Get Corporate Filings Examples

**Basic Request**
```bash
curl -X GET "https://fin.anshulkr.com/api/corporate_filings" \
  -H "Authorization: Bearer your_access_token"
```

**Filtered Request with Date Range**
```bash
curl -X GET "https://fin.anshulkr.com/api/corporate_filings?start_date=2025-01-01&end_date=2025-05-20&category=Financial%20Results&symbol=AAPL" \
  -H "Authorization: Bearer your_access_token"
```

**Request Including Procedural Filings**
```bash
curl -X GET "https://fin.anshulkr.com/api/corporate_filings?start_date=2025-01-01&category=Procedural/Administrative" \
  -H "Authorization: Bearer your_access_token"
```

**Filter by Multiple Parameters**
```bash
curl -X GET "https://fin.anshulkr.com/api/corporate_filings?category=Board%20Meeting&isin=US0378331005&start_date=2025-03-01" \
  -H "Authorization: Bearer your_access_token"
```

**Filter by Multiple Categories**
```bash
curl -X GET "https://fin.anshulkr.com/api/corporate_filings?category=Board%20Meeting,Annual%20Report,Financial%20Results&start_date=2025-03-01" \
  -H "Authorization: Bearer your_access_token"
```

**Filter by Multiple Symbols**
```bash
curl -X GET "https://fin.anshulkr.com/api/corporate_filings?symbol=AAPL,MSFT,GOOGL&start_date=2025-01-01" \
  -H "Authorization: Bearer your_access_token"
```

**Filter by Multiple ISINs**
```bash
curl -X GET "https://fin.anshulkr.com/api/corporate_filings?isin=US0378331005,US5949181045,US02079K1079&end_date=2025-05-20" \
  -H "Authorization: Bearer your_access_token"
```

**Combined Multiple Filters**
```bash
curl -X GET "https://fin.anshulkr.com/api/corporate_filings?category=Financial%20Results,Dividend&symbol=AAPL,TSLA&start_date=2025-01-01&end_date=2025-05-20&page=635" \
  -H "Authorization: Bearer your_access_token"
```

#### Response Structure

**Success Response (200 OK)**
```json
{
  "count": 15,
  "current_page": 635,
  "filings": [
    {
      "corp_id": "corp-123",
      "securityid": "12345",
      "summary": "Apple Inc. announces financial results for Q1 2025",
      "fileurl": "https://example.com/filing.pdf",
      "date": "2025-04-28T14:30:00.000Z",
      "ai_summary": "**Category:** Financial Results\n**Headline:** Q1 2025 Results\n\nApple Inc. announces financial results for Q1 2025 with a 12% increase in revenue.",
      "category": "Financial Results",
      "isin": "US0378331005",
      "companyname": "Apple Inc.",
      "symbol": "AAPL",
      "headline": "Apple Inc. announces financial results for Q1 2025 with a growth of 20%",
      "sentiment": "Positive",
      "investorCorp": [
        {
          "id": "inv-456",
          "investor_id": "investor-789",
          "investor_name": "Institutional Investor ABC",
          "aliasBool": false,
          "aliasName": null,
          "verified": true,
          "type": "institutional",
          "alias_id": null
        }
      ]
    }
  ],
  "has_next": true,
  "has_previous": true,
  "page_size": 15,
  "total_count": 9605,
  "total_pages": 641,
  "verified: false
}
```

**Fallback Response (with Note)**
```json
{
  "count": 5,
  "filings": [...],
  "note": "Date filters were ignored to return results"
}
```

**Test Data Response**
```json
{
  "count": 10,
  "filings": [...],
  "note": "Using test data as fallback"
}
```

#### Error Responses

**Invalid Date Format (400 Bad Request)**
```json
{
  "message": "Invalid start_date format. Use YYYY-MM-DD",
  "status": "error"
}
```

**Database Unavailable (503 Service Unavailable)**
```json
{
  "message": "Database service unavailable. Please try again later.",
  "status": "error"
}
```

#### Get Filing by ID Example
```bash
curl -X GET https://fin.anshulkr.com/api/corporate_filings/corp-123
```

#### Response
```json
{
  "corp_id": "corp-123",
  "summary": "Apple Inc. announces financial results for Q1 2025",
  "category": "Financial Results",
  "isin": "US0378331005",
  "companyname": "Apple Inc.",
  "symbol": "AAPL",
  "date": "2025-04-28T14:30:00.000Z",
  "ai_summary": "**Category:** Financial Results\n**Headline:** Q1 2025 Results\n\nApple Inc. announces financial results for Q1 2025 with a 12% increase in revenue.",
  "headline": "Apple Inc. announces financial results for Q1 2025 with a growth of 20%",
  "sentiment": "Positive",
  "fileurl": "https://example.com/filing.pdf"
}
```

#### Fallback Mechanisms

The API implements multiple fallback mechanisms to ensure reliability:

1. **Primary Query**: Full query with all filters applied
2. **Simplified Query**: If no results, retry without date filters but keep other filters
3. **Test Data**: If database queries fail, return generated test data
4. **Error Handling**: Comprehensive error logging and user-friendly error messages

#### Common Categories

- Financial Results
- Board Meeting
- Procedural/Administrative
- Corporate Governance
- Shareholding Pattern
- Dividend
- Annual Report
- Investor Presentation
- Material Events
- Regulatory Filing

#### Performance Considerations

- Results are ordered by date (most recent first)
- Automatic exclusion of procedural/administrative filings unless explicitly requested
- Efficient database queries with proper indexing
- Fallback mechanisms prevent API downtime


### Bulk and Block Deals

Retrieve bulk and block deals from NSE and BSE with comprehensive filtering options.

**Authentication Required:** This endpoint requires a valid Bearer token.

```bash
# Get all deals (default: 50 per page)
curl -X GET http://localhost:5001/api/deals \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Filter by exchange
curl -X GET "http://localhost:5001/api/deals?exchange=NSE" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Filter by deal type (BULK or BLOCK)
curl -X GET "http://localhost:5001/api/deals?deal=BULK" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Filter by buy/sell
curl -X GET "http://localhost:5001/api/deals?deal_type=BUY" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Filter by date range
curl -X GET "http://localhost:5001/api/deals?start_date=2025-11-01&end_date=2025-11-22" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Filter by symbol (partial match)
curl -X GET "http://localhost:5001/api/deals?symbol=RELIANCE" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Combined filters with pagination
curl -X GET "http://localhost:5001/api/deals?exchange=BSE&deal=BULK&deal_type=BUY&start_date=2025-11-20&page=2&page_size=100" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Query Parameters:**
- `exchange` (optional): Filter by exchange - NSE or BSE
- `deal` (optional): Filter by deal type - BULK or BLOCK
- `deal_type` (optional): Filter by transaction type - BUY or SELL
- `start_date` (optional): Start date in YYYY-MM-DD format
- `end_date` (optional): End date in YYYY-MM-DD format
- `symbol` (optional): Filter by stock symbol (partial match, case-insensitive)
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 50, max: 500)

**Response:**
```json
{
  "success": true,
  "deals": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "symbol": "RELIANCE",
      "securityid": "500325",
      "date": "2025-11-21",
      "client_name": "ABC SECURITIES LIMITED",
      "deal_type": "BUY",
      "quantity": 150000,
      "price": "2850.50",
      "exchange": "BSE",
      "deal": "BULK",
      "created_at": "2025-11-22T10:30:00.000Z"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440002",
      "symbol": "TCS",
      "securityid": "532540",
      "date": "2025-11-21",
      "client_name": "XYZ TRADING COMPANY",
      "deal_type": "SELL",
      "quantity": 50000,
      "price": "3420.75",
      "exchange": "BSE",
      "deal": "BLOCK",
      "created_at": "2025-11-22T10:35:00.000Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_count": 217,
    "total_pages": 5,
    "has_next": true,
    "has_prev": false
  },
  "filters": {
    "exchange": null,
    "deal": null,
    "deal_type": null,
    "start_date": null,
    "end_date": null,
    "symbol": null
  }
}
```

### Company Search

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/company/search` | GET | Search for companies | No |

#### Search Companies Example
```bash
curl -X GET "https://fin.anshulkr.com/api/company/search?q=Apple&limit=5"
```

#### Response
```json
{
  "count": 1,
  "companies": [
    {
      "newname": "Apple Inc.",
      "oldname": "Apple Computer, Inc.",
      "newnsecode": "AAPL",
      "oldnsecode": "AAPL",
      "newbsecode": "AAPL",
      "oldbsecode": "AAPL",
      "isin": "US0378331005"
    }
  ]
}
```


## Insider Trading Data

### Get Insider Trading Records

Retrieve insider trading data with automatic filtering based on exchange-specific criteria.

**Endpoint:** `GET /api/insider_trading`

**Authentication:** Required (Bearer token)

**Query Parameters:**
- `exchange` (optional): Filter by exchange - `NSE` or `BSE`
- `start_date` (optional): Filter from date (YYYY-MM-DD format)
- `end_date` (optional): Filter until date (YYYY-MM-DD format)
- `symbol` (optional): Filter by stock symbol
- `sec_code` (optional): Filter by security code
- `person_name` (optional): Filter by person name
- `page` (optional): Page number for pagination (default: 1)
- `page_size` (optional): Items per page (default: 50, max: 500)

**Automatic Filters Applied:**

When `exchange` parameter is specified, the API automatically applies exchange-specific filters:

**BSE Records** - Only includes transactions with:
- **mode_acq** (42 approved modes): Market Purchase, Market Sale, Pledge Creation, Revocation Of Pledge, Invocation Of Pledged, Block Deal, Transfer, Preferential Offer, Preferential Issue, Conv. of Warrants, Invocation of pledge, Shares Purchased, Conversion Of Compulsory Convertible Preference Shares, Physical Share Transfer, Allotment Of Bonus Shares, and 27 more acquisition modes
- **person_cat** (8 categories): Promoter Group, Promoter, Director, Promoter & Director, Promoters Immediate Relative, Promoter and Director, Member of Promoter Group, Promoter Immediate Relative
- **post_sec_type** (4 types): Equity, Warrants, Preference Shares, Convertible Warrants

**NSE Records** - Only includes transactions with:
- **mode_acq** (6 approved modes): Pledge Creation, Market Purchase, Market Sale, Revokation of Pledge, Invocation of pledge, market purchases
- **person_cat** (8 categories): Promoter Group, Promoters, Promoter, Chairman and Managing Director, Promoters Immediate Relative, Member of Promoter Group, Promoter & Director, Promoters & Promoters Group
- **post_sec_type** (10 types): Equity Shares, Warrants, Preference Shares, Convertible preference shares, Equity, Shares, Equity Share, Compulsorily Convertible Preference Shares, Share, Equity  Shares

**When no exchange is specified**: Returns records from both BSE and NSE that match their respective filter criteria. This allows you to get all qualifying insider trading activity across both exchanges in a single request.

**Example Request:**
```bash
# Get today's BSE insider trading
curl -X GET "http://localhost:5001/api/insider_trading?exchange=BSE&start_date=2025-11-24&end_date=2025-11-24" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get NSE insider trading for a specific symbol
curl -X GET "http://localhost:5001/api/insider_trading?exchange=NSE&symbol=RELIANCE&start_date=2025-11-01" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get all insider trading from both exchanges with pagination
curl -X GET "http://localhost:5001/api/insider_trading?start_date=2025-11-01&page=1&page_size=100" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Search by person name
curl -X GET "http://localhost:5001/api/insider_trading?person_name=AMBANI&exchange=BSE" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "insider_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "sec_code": "500325",
      "sec_name": "Reliance Industries Limited",
      "symbol": "RELIANCE",
      "person_name": "MUKESH D AMBANI",
      "person_cat": "Promoter",
      "pre_sec_type": "Equity Shares",
      "pre_sec_num": 5000000,
      "pre_sec_pct": 2.5,
      "trans_sec_type": "Equity Shares",
      "trans_sec_num": 100000,
      "trans_value": 25000000.00,
      "trans_type": "Acquisition",
      "post_sec_type": "Equity",
      "post_sec_num": 5100000,
      "post_sec_pct": 2.55,
      "date_from": "2025-11-24",
      "date_to": "2025-11-24",
      "date_intimation": "2025-11-24",
      "mode_acq": "Market Purchase",
      "exchange": "BSE"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_count": 150,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  },
  "filters": {
    "exchange": "BSE",
    "start_date": "2025-11-24",
    "end_date": "2025-11-24",
    "symbol": null,
    "sec_code": null,
    "person_name": null
  }
}
```

**Response Fields:**
- `insider_uuid`: Unique identifier for the record
- `sec_code`: Security code (populated automatically for NSE from symbol)
- `sec_name`: Security/company name
- `symbol`: Stock symbol (populated automatically for BSE from sec_code)
- `person_name`: Name of the person involved in the transaction
- `person_cat`: Category of person (Promoter, Director, etc.)
- `pre_sec_num`: Number of securities held before transaction
- `pre_sec_pct`: Percentage of securities held before transaction
- `trans_sec_num`: Number of securities in the transaction
- `trans_value`: Value of the transaction
- `trans_type`: Transaction type (Acquisition/Disposal)
- `post_sec_num`: Number of securities held after transaction
- `post_sec_pct`: Percentage of securities held after transaction
- `date_from`: Transaction start date
- `date_to`: Transaction end date
- `date_intimation`: Date of intimation to company
- `mode_acq`: Mode of acquisition/disposal
- `exchange`: Exchange (BSE/NSE)

**Notes:**
- For **BSE** records, `symbol` is automatically populated from `stocklistdata` table using `sec_code` via database trigger
- For **NSE** records, `sec_code` is automatically populated from `stocklistdata` table using `symbol` via database trigger
- All data is deduplicated with BSE records taking priority when duplicates exist
- Filters are case-insensitive for text searches

**Error Responses:**

401 Unauthorized (Missing/Invalid Token):
```json
{
  "message": "Authentication token is missing!"
}
```

400 Bad Request (Invalid Exchange):
```json
{
  "success": false,
  "message": "Invalid exchange. Must be NSE or BSE."
}
```

400 Bad Request (Invalid Parameters):
```json
{
  "success": false,
  "message": "Invalid parameter: page must be a positive integer"
}
```

500 Internal Server Error:
```json
{
  "success": false,
  "message": "Failed to fetch insider trading data: <error details>"
}
```

## Stock Price Data

A RESTful API service for retrieving historical stock price data using International Securities Identification Numbers (ISIN).

## Overview

This API provides access to historical stock price data from global exchanges. It allows authenticated users to retrieve closing prices for stocks using their ISIN identifiers.

Key features:
- Authenticated access to stock price data
- Historical closing prices with dates
- Lookup by International Securities Identification Number (ISIN)
- Data ordered by date (most recent first)

## Authentication

All API requests require authentication using a Bearer token.

Include the following header with all requests:
```
Authorization: Bearer YOUR_TOKEN_HERE
```

To obtain an API token, contact the system administrator or register through the developer portal.

## API Endpoints

### Stock Price

#### `GET /api/stock_price`

Retrieves historical stock price data for a specified security.

**Parameters:**

| Parameter | Type   | Required | Description                                     |
|-----------|--------|----------|-------------------------------------------------|
| isin      | string | Yes      | International Securities Identification Number   |
| range.    | string | max.     | The date range for the historical data. Valid options are: <ul><li>1w (1 week)</li><li>1m (1 month)</li><li>3m (3 months)</li><li>6m (6 months)</li><li>1y (1 year)</li><li>max (all available data)</li></ul> |

**Response:**

A JSON array of objects containing close prices and dates, ordered by date (most recent first).

**Success Response (200 OK):**

```json
[
  {
    "close": 142.56,
    "date": "2025-05-19"
  },
  {
    "close": 140.32,
    "date": "2025-05-18"
  },
  ...
]
```

**Error Responses:**

| Status Code | Message                      | Description                                |
|-------------|-----------------------------|---------------------------------------------|
| 400         | Missing isin parameter!     | The required ISIN parameter was not provided |
| 401         | Unauthorized                | Authentication token is missing or invalid   |
| 404         | No stock price data found!  | No data exists for the provided ISIN        |
| 429         | Too many requests           | Rate limit exceeded                         |
| 500         | Failed to retrieve stock price! | Server error occurred during data retrieval |

## Error Handling

The API uses standard HTTP status codes to indicate the success or failure of requests. Error responses include a JSON object with a `message` field providing details about the error.

Example error response:
```json
{
  "message": "Missing isin parameter!"
}
```

## Examples

### Example Request

```bash
curl -X GET "https://fin.anshulkr.com/api/stock_price?isin=US0378331005&range=1m" \
  -H "Authorization: Bearer your_token_here"
```

### Example Response

```json
[
  {
    "close": 195.42,
    "date": "2025-05-19"
  },
  {
    "close": 193.87,
    "date": "2025-05-16"
  },
  {
    "close": 194.05,
    "date": "2025-05-15"
  }
]
```

### Announcements

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/save_announcement` | POST | Save announcement to database | Yes |
| `/api/insert_new_announcement` | POST | Insert and broadcast announcement | No |
| `/api/test_announcement` | POST | Send test announcement via WebSocket | No |
| `/calc_price_diff` | GET | Calculate price difference for saved item | Yes |

# API Endpoints

## Save Announcement

Saves announcements or large deals to the database with stock price tracking.

#### Save Announcement Example
```bash
curl -X POST https://fin.anshulkr.com/api/save_announcement \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_access_token" \
  -d '{
    "item_type": "ANNOUNCEMENT",
    "item_id": "corp-123",
    "isin": "US0378331005",
    "note": "Important announcement"
  }'
```

#### Save Large Deal Example
```bash
curl -X POST https://fin.anshulkr.com/api/save_announcement \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_access_token" \
  -d '{
    "item_type": "LARGE_DEALS",
    "item_id": "deal-456",
    "isin": "US0378331005",
    "note": "Major acquisition deal"
  }'
```

**Required Fields:**
- `item_type`: Must be either "ANNOUNCEMENT" or "LARGE_DEALS"
- `item_id`: Unique identifier for the item
- `isin`: International Securities Identification Number

**Optional Fields:**
- `note`: Additional notes (defaults to empty string)

**Response:**
```json
{
  "message": "Item saved successfully",
  "status": "success",
  "data": {
    "saved_item": {
      "user_id": 123,
      "item_type": "ANNOUNCEMENT",
      "related_announcement_id": "corp-123",
      "note": "Important announcement",
      "saved_price": 150.75,
      "saved_at": "2025-08-05T10:30:00"
    },
    "stock_price": 150.75
  }
}
```

## Fetch Saved Announcements

Retrieves all saved announcements and large deals for the authenticated user.

#### Fetch Saved Announcements Example
```bash
curl -X GET https://fin.anshulkr.com/api/fetch_saved_announcements \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_access_token"
```

**Response:**
```json
{
  "message": "Saved announcements fetched successfully",
  "status": "success",
  "data": [
    {
      "ai_summary": null,
      "category": "Procedural/Administrative",
      "companyname": "Pilani Investment and Industries Corporation Limited",
      "corp_id": "000c3ff0-4448-4a0c-a7b6-b9fc0bdb2de3",
      "date": "2025-06-30T20:25:31",
      "fileurl": "https://nsearchives.nseindia.com/corporate/PILANIINVS_30062025202329_Pilani_AGM_proceedings_30062025.pdf",
      "headline": null,
      "id": "da40c318-ff9c-4f90-918a-3e7dffc8cf1d",
      "investors": [],
      "isin": "INE417C01014",
      "note": "Saving corp_id 2",
      "saved_at": "2025-08-05T12:47:44.808068+00:00",
      "securityid": "539883",
      "sentiment": null,
      "summary": "Pilani Investment and Industries Corporation Limited has informed the Exchange regarding Proceedings of Annual General Meeting held on Jun 30, 2025",
      "symbol": "PILANIINVS",
      "user_id": "a4147001-ab8f-4913-9495-7e968c4f51ca"
    },
    {
      "ai_summary": "### Q1 FY26 Financial Highlights\n\nSavita Oil Technologies Ltd. presented its Q1 FY26 financial highlights, showcasing a robust performance with a Year-on-Year growth of 41% in Profit Before Tax (PBT). Overall sales volumes remained steady, supported by healthy double-digit growth in domestic sales...",
      "category": "Investor Presentation",
      "companyname": "Savita Oil Technologies Ltd",
      "corp_id": "e515c4dc-69d3-437b-a1e3-7fb884f1dd51",
      "date": "2025-08-16T10:26:20",
      "fileurl": "https://www.bseindia.com/xml-data/corpfiling/AttachLive/3d3dddb7-daaf-432b-8a62-9754429ec8e6.pdf",
      "headline": "Savita Oil Technologies Ltd. reports robust Q1 FY26 performance with 41% YoY PBT growth; Revenue crosses ₹1,000 Cr for second consecutive quarter.",
      "id": "18238b8e-d765-46eb-9b27-05704969d2be",
      "investors": [
        {
          "aliasBool": "False",
          "aliasName": "",
          "alias_id": null,
          "investor_id": "4e020f16-dca8-443f-bf48-6b8c2f58beb9",
          "investor_name": "BHEL",
          "type": "institution",
          "verified": "false"
        },
        {
          "aliasBool": "False",
          "aliasName": "",
          "alias_id": null,
          "investor_id": "d1d63888-0e60-452b-8613-7b9d40784f60",
          "investor_name": "TATA MOTORS",
          "type": "institution",
          "verified": "false"
        }
      ],
      "isin": "INE035D01020",
      "note": "Saving corp_id 1",
      "saved_at": "2025-08-05T12:47:05.708566+00:00",
      "securityid": "524667",
      "sentiment": "Positive",
      "summary": "Investor Presentation of Q1 FY 2025-26 is enclosed",
      "symbol": "SOTL",
      "user_id": "a4147001-ab8f-4913-9495-7e968c4f51ca"
    }
  ]
}
```

**Response Fields:**
- `ai_summary`: AI-generated comprehensive summary (may be null or very detailed)
- `category`: Type/category of the announcement (e.g., "Procedural/Administrative", "Investor Presentation")
- `companyname`: Full company name
- `corp_id`: Corporate filing identifier
- `date`: Original announcement date (ISO format)
- `fileurl`: URL to the original document/filing (PDF or other formats)
- `headline`: Announcement headline (may be null or detailed description)
- `id`: Unique identifier for the saved item
- `investors`: Array of related investor information with the following structure:
  - `aliasBool`: Whether the investor has an alias (string: "True"/"False")
  - `aliasName`: Alias name if applicable (may be empty string)
  - `alias_id`: Alias identifier (may be null)
  - `investor_id`: Unique investor identifier
  - `investor_name`: Name of the investor/institution
  - `type`: Type of investor (e.g., "institution")
  - `verified`: Verification status (string: "true"/"false")
- `isin`: International Securities Identification Number
- `note`: User's personal note when saving the item
- `saved_at`: Timestamp when item was saved (ISO format with timezone)
- `securityid`: Security identifier from exchange
- `sentiment`: Sentiment analysis result (may be null, "Positive", "Negative", "Neutral")
- `summary`: Brief summary of the announcement
- `symbol`: Stock trading symbol
- `user_id`: User identifier who saved the item

**Empty Response (No saved items):**
```json
{
  "message": "No saved announcements found",
  "status": "success",
  "data": []
}
```

**Notes:**
- The `ai_summary` field can contain extensive markdown-formatted content with financial highlights, metrics, and detailed analysis
- The `investors` array may be empty for some announcements or contain multiple institutional investors
- All timestamp fields include timezone information (+00:00 format)
- The `headline` field can contain detailed descriptions and may include special characters (₹ symbol)

## Authentication

Both endpoints require authentication using Bearer tokens in the Authorization header:
```
Authorization: Bearer your_access_token
```

## Error Responses

Both endpoints return consistent error responses:
```json
{
  "message": "Error description",
  "status": "error"
}
```

Common HTTP status codes:
- `400`: Bad Request (missing/invalid fields)
- `404`: Not Found (no stock data available)
- `500`: Server Error (database or calculation errors)

#### Insert New Announcement Example
```bash
curl -X POST https://fin.anshulkr.com/api/insert_new_announcement \
  -H "Content-Type: application/json" \
  -d '{
    "corp_id": "corp-123",
    "summary": "Company announces new product",
    "category": "Product Launch",
    "isin": "US0378331005",
    "companyname": "Example Corp",
    "symbol": "EXPL",
    "date": "2025-01-30T10:00:00Z",
    "ai_summary": "**Category:** Product Launch\n**Headline:** New Product\n\nExample Corp announces new product launch."
  }'
```


### Admin Endpoints

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/users` | GET | List all users (admin) | No |

#### List All Users Example
```bash
curl -X GET https://fin.anshulkr.com/api/users
```

#### Response
```json
{
  "count": 2,
  "users": [
    {
      "UserID": "f8a92dc1-5e42-4b67-b4d9-e8a317f8e2a3",
      "emailID": "user@example.com",
      "Phone_Number": null,
      "Paid": "false",
      "AccountType": "free",
      "created_at": "2025-01-30T10:00:00.000Z"
    }
  ]
}
```

### System Status

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/socket/health` | GET | Check Socket.IO server health | No |
| `/api/scraper_status` | GET | Check scraper thread status | No |

#### Socket Health Check Example
```bash
curl -X GET https://fin.anshulkr.com/api/socket/health
```

#### Response
```json
{
  "socket_server_running": true,
  "socketio_initialized": true,
  "async_mode": "eventlet",
  "server_available": true,
  "status": "healthy"
}
```

#### Scraper Status Example
```bash
curl -X GET https://fin.anshulkr.com/api/scraper_status
```

#### Response
```json
{
  "threads_started": true,
  "thread_count": 2,
  "threads": [
    {
      "name": "BSE-Scraper",
      "alive": true,
      "daemon": false
    },
    {
      "name": "NSE-Scraper",
      "alive": true,
      "daemon": false
    }
  ]
}
```

The API will be available at `http://127.0.0.1:5001/`.

## WebSocket Integration

The server provides real-time updates via WebSockets using Socket.IO. Clients can subscribe to announcement channels and receive notifications when new corporate filings are published.

### Connecting to WebSocket

Using JavaScript with Socket.IO client:

```javascript
const socket = io('https://fin.anshulkr.com');

socket.on('connect', () => {
  console.log('Connected to server');
});

// Listen for new announcements
socket.on('new_announcement', (data) => {
  console.log('New announcement received:', data);
});

// Join a specific room (e.g., for specific categories or companies)
socket.emit('join', { room: 'financial_results' });
```

### Available WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `connect` | client ← server | Connection established |
| `status` | client ← server | Connection status update |
| `join` | client → server | Join a specific room |
| `leave` | client → server | Leave a specific room |
| `new_announcement` | client ← server | New corporate filing/announcement |

## Data Models

### User Data

```
UserData Table
- UserID (UUID, Primary Key)
- emailID (Text)
- Password (Hashed Text)
- Phone_Number (Text, Optional)
- Paid (Text: 'true'/'false')
- AccountType (Text: 'free'/'premium')
- created_at (Timestamp)
- AccessToken (Text)
- WatchListID (JSON Array)
- emailData (JSON Array, Optional)
```

### Watchlist Data

```
watchlistnamedata Table
- watchlistid (UUID, Primary Key)
- watchlistname (Text)
- userid (Text)

watchlistdata Table
- watchlistid (UUID, Foreign Key to watchlistnamedata)
- isin (Text, NULL for category rows)
- category (Text, NULL for ISIN rows)
- userid (Text)
```

### Corporate Filings

```
corporatefilings Table
- corp_id (Text, Primary Key)
- securityid (Text)
- summary (Text)
- fileurl (Text, Optional)
- date (Timestamp)
- ai_summary (Text)
- category (Text)
- isin (Text)
- companyname (Text)
- symbol (Text)
- headline (Text, Optional)
- sentiment (Text, Optional)
```

### Company Data

```
stocklistdata Table
- newname (Text)
- oldname (Text)
- newnsecode (Text)
- oldnsecode (Text)
- newbsecode (Text)
- oldbsecode (Text)
- isin (Text)
```

### Stock Price Data

```
stockpricedata Table
- isin (Text)
- close (Numeric)
- date (Date)
```

### Saved Items

```
save_items Table
- user_id (Text)
- item_type (Text)
- related_announcement_id (Text, Optional)
- related_deal_id (Text, Optional)
- note (Text, Optional)
- saved_price (Numeric)
```

## Error Handling

The API uses consistent error responses with appropriate HTTP status codes:

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

### Error Response Format

```json
{
  "message": "Description of the error",
  "status": "error"
}
```

## Testing

A comprehensive test script (`watchlist_api_test.py`) is available to test all watchlist API endpoints. This script:

1. Registers a new test user
2. Tests all watchlist operations (create, add ISINs, remove ISINs, clear, delete)
3. Provides detailed logs and verification of operations

### Running the Test Script

```bash
python watchlist_api_test.py
```

### Sample Test Output

```
[TEST] Registering user: test_user_1716202356@example.com
Status Code: 201
Response: {
  "message": "User registered successfully!",
  "user_id": "f8a92dc1-5e42-4b67-b4d9-e8a317f8e2a3",
  "token": "a8b7c6d5e4f3..."
}
✅ User registered successfully. User ID: f8a92dc1-5e42-4b67-b4d9-e8a317f8e2a3

...

============================================
Watchlist API Tests Summary
============================================
Register: ✅ PASSED
Login: ✅ PASSED
Create Watchlists: ✅ PASSED
Add Isins: ✅ PASSED
Set Categories: ✅ PASSED
Get Watchlists: ✅ PASSED
Remove Isins: ✅ PASSED
Clear Watchlist: ✅ PASSED
Delete Watchlist: ✅ PASSED

============================================
Overall Success Rate: 100.00% (9/9)
============================================
```

## Deployment

### Production Considerations

1. **Environment Variables**:
   - Set `DEBUG_MODE=false` for production
   - Use strong random values for `PASSWORD_SALT`
   
2. **Security**:
   - Use HTTPS in production
   - Set appropriate CORS restrictions
   - Consider adding rate limiting

3. **Performance**:
   - Increase Socket.IO ping timeout for stable connections
   - Consider using a production-ready WSGI server like Gunicorn

### Docker Deployment

A sample Dockerfile is available in the repository. To build and run:

```bash
docker build -t financial-backend .
docker run -p 5001:5001 \
  -e SUPABASE_URL2=your_supabase_url \
  -e SUPABASE_KEY2=your_supabase_key \
  -e PASSWORD_SALT=your_salt \
  financial-backend
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**:
   - Verify Supabase credentials are correct
   - Check if the tables exist in the database

2. **Authentication Issues**:
   - Ensure the token is included in the Authorization header
   - Verify the token format: `Bearer YOUR_TOKEN`

3. **WebSocket Connection Problems**:
   - Check for CORS issues
   - Verify client Socket.IO version compatibility

4. **Scraper Issues**:
   - Check scraper status at `/api/scraper_status`
   - Verify scraper files (`new_scraper.py`, `nse_scraper.py`) exist
   - Check log files for scraper errors

5. **Corporate Filings Issues**:
   - Check database connectivity first
   - Verify date format (YYYY-MM-DD)
   - Test with fallback endpoints if primary queries fail
   - Review logs for detailed error information

6. **Multiple Categories Issues**:
   - Ensure `categories` is sent as an array, not a string
   - Verify each category string is properly formatted
   - Check for proper JSON encoding in requests
   - Review response for details on successful/failed categories

### Debugging

For additional debugging, set `DEBUG_MODE=true` and check the server logs for detailed information about requests, responses, and errors. The Corporate Filings API provides comprehensive logging for all query attempts and fallback mechanisms.

---

For additional help, please open an issue in the repository or contact the development team.