# Financial Backend API Documentation

A comprehensive Flask-based REST API for financial data management, user authentication, watchlists, corporate filings, announcement tracking, and real-time financial data processing. This API serves as the backbone for financial applications requiring robust data management, user authentication, and real-time updates.

## 🚀 Features

- **User Authentication & Authorization**: Custom token-based authentication system
- **Watchlist Management**: Create, manage, and track multiple watchlists with ISINs and categories
- **Corporate Filings**: Access and filter corporate announcements with AI-powered summaries
- **Stock Price Tracking**: Real-time and historical stock price data with multiple time ranges
- **Saved Announcements**: Save, annotate, and track price changes for important announcements
- **Real-time Updates**: Socket.IO integration for live data streaming
- **Price Calculation**: Automatic price difference calculations for saved items
- **Search Functionality**: Advanced company and filing search capabilities
- **Bulk Operations**: Efficient bulk addition of watchlist items
- **AI Integration**: AI-powered analysis and categorization of financial data

## 📋 Table of Contents

- [🚀 Features](#-features)
- [⚙️ Installation & Setup](#️-installation--setup)
- [🏃 Quick Start](#-quick-start)
- [🔐 Authentication](#-authentication)
- [📡 API Endpoints](#-api-endpoints)
  - [🏥 Health Check](#-health-check)
  - [👤 User Management](#-user-management)
  - [📊 Watchlist Management](#-watchlist-management)
  - [📄 Corporate Filings](#-corporate-filings)
  - [💹 Stock Price Data](#-stock-price-data)
  - [💾 Saved Announcements](#-saved-announcements)
  - [🔍 Company Search](#-company-search)
  - [🔌 Real-time WebSocket](#-real-time-websocket)
- [⚠️ Error Handling](#️-error-handling)
- [🔧 Advanced Configuration](#-advanced-configuration)
- [🚀 Deployment](#-deployment)
- [🐛 Troubleshooting](#-troubleshooting)
- [📈 Performance Optimization](#-performance-optimization)
- [🔒 Security Considerations](#-security-considerations)
- [🧪 Testing](#-testing)

## Getting Started

### Base URL
```
http://localhost:5001/api
```

### Content Type
All requests should include the `Content-Type: application/json` header for POST/PUT requests.

### CORS
The API supports CORS and accepts requests from any origin with all standard HTTP methods.

## Authentication

The API uses custom token-based authentication. Most endpoints require an `Authorization` header with a Bearer token.

### Header Format
```
Authorization: Bearer <your_access_token>
```

## API Endpoints

### Health Check

#### Check API Health
```bash
curl -X GET http://localhost:5001/api/health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-10-16T10:30:00.000Z",
  "server": "Financial Backend API (Custom Auth)",
  "supabase_connected": true,
  "debug_mode": false,
  "environment": {
    "supabase_url_set": true,
    "supabase_key_set": true
  }
}
```

---

## User Management

### Register New User

```bash
curl -X POST http://localhost:5001/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123",
    "phone": "+1234567890",
    "account_type": "free"
  }'
```

**Response:**
```json
{
  "message": "User registered successfully!",
  "status": "success",
  "data": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "access_token": "a1b2c3d4e5f6...",
    "account_type": "free"
  }
}
```

### User Login

```bash
curl -X POST http://localhost:5001/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

**Response:**
```json
{
  "message": "Login successful!",
  "status": "success",
  "data": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "access_token": "a1b2c3d4e5f6...",
    "email": "user@example.com",
    "account_type": "free"
  }
}
```

### Get User Profile

```bash
curl -X GET http://localhost:5001/api/user \
  -H "Authorization: Bearer <your_access_token>"
```

**Response:**
```json
{
  "UserID": "550e8400-e29b-41d4-a716-446655440000",
  "emailID": "user@example.com",
  "Phone_Number": "+1234567890",
  "Paid": "false",
  "AccountType": "free",
  "created_at": "2025-10-16T10:30:00.000Z",
  "WatchListID": "660e8400-e29b-41d4-a716-446655440001"
}
```

### Update User Profile

```bash
curl -X PUT http://localhost:5001/api/update_user \
  -H "Authorization: Bearer <your_access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "Phone_Number": "+1987654321",
    "current_password": "oldpassword",
    "new_password": "newpassword123"
  }'
```

**Response:**
```json
{
  "message": "User profile updated successfully!",
  "status": "success"
}
```

### User Logout

```bash
curl -X POST http://localhost:5001/api/logout \
  -H "Authorization: Bearer <your_access_token>"
```

**Response:**
```json
{
  "message": "Logout successful!",
  "status": "success"
}
```

### Validate Token

```bash
curl -X POST http://localhost:5001/api/check_valid_token \
  -H "Authorization: Bearer <your_access_token>"
```

**Response:**
```json
{
  "message": "Token is valid!"
}
```

---

## Watchlist Management

### Get User Watchlists

```bash
curl -X GET http://localhost:5001/api/watchlist \
  -H "Authorization: Bearer <your_access_token>"
```

**Response:**
```json
{
  "watchlists": [
    {
      "_id": "660e8400-e29b-41d4-a716-446655440001",
      "watchlistName": "Real Time Alerts",
      "categories": ["Technology", "Banking"],
      "isin": ["INE009A01021", "INE090A01013"]
    }
  ]
}
```

### Create New Watchlist

```bash
curl -X POST http://localhost:5001/api/watchlist \
  -H "Authorization: Bearer <your_access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "create",
    "watchlistName": "My Tech Stocks",
    "watchlistType": "DS"
  }'
```

**Response:**
```json
{
  "message": "Watchlist created successfully!",
  "status": "success",
  "data": {
    "watchlist_id": "770e8400-e29b-41d4-a716-446655440002",
    "watchlist_name": "My Tech Stocks"
  }
}
```

### Add ISIN/Category to Watchlist

```bash
curl -X POST http://localhost:5001/api/watchlist \
  -H "Authorization: Bearer <your_access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "add_isin",
    "watchlist_id": "660e8400-e29b-41d4-a716-446655440001",
    "isin": "INE009A01021",
    "categories": ["Technology"]
  }'
```

**Response:**
```json
{
  "message": "Items added to watchlist successfully!",
  "watchlist_id": "660e8400-e29b-41d4-a716-446655440001",
  "isin_added": "INE009A01021",
  "categories_added": ["Technology"]
}
```

### Bulk Add ISINs

```bash
curl -X POST http://localhost:5001/api/watchlist/bulk_add \
  -H "Authorization: Bearer <your_access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "watchlist_id": "660e8400-e29b-41d4-a716-446655440001",
    "isins": ["INE009A01021", "INE090A01013", "INE002A01018"],
    "categories": ["Technology", "Banking"]
  }'
```

**Response:**
```json
{
  "message": "Added 3 ISINs successfully",
  "successful": ["INE009A01021", "INE090A01013", "INE002A01018"],
  "duplicates": [],
  "failed": [],
  "watchlist": {
    "_id": "660e8400-e29b-41d4-a716-446655440001",
    "watchlistName": "Real Time Alerts",
    "categories": ["Technology", "Banking"],
    "isin": ["INE009A01021", "INE090A01013", "INE002A01018"]
  }
}
```

### Remove ISIN from Watchlist

```bash
curl -X DELETE http://localhost:5001/api/watchlist/660e8400-e29b-41d4-a716-446655440001/isin/INE009A01021 \
  -H "Authorization: Bearer <your_access_token>"
```

**Response:**
```json
{
  "message": "ISIN removed from watchlist!",
  "watchlist": {
    "_id": "660e8400-e29b-41d4-a716-446655440001",
    "watchlistName": "Real Time Alerts",
    "category": "Technology",
    "isin": ["INE090A01013", "INE002A01018"]
  }
}
```

### Delete Watchlist

```bash
curl -X DELETE http://localhost:5001/api/watchlist/660e8400-e29b-41d4-a716-446655440001 \
  -H "Authorization: Bearer <your_access_token>"
```

**Response:**
```json
{
  "message": "Watchlist deleted successfully!",
  "watchlists": []
}
```

### Clear Watchlist

```bash
curl -X POST http://localhost:5001/api/watchlist/660e8400-e29b-41d4-a716-446655440001/clear \
  -H "Authorization: Bearer <your_access_token>"
```

**Response:**
```json
{
  "message": "Watchlist cleared successfully!",
  "watchlist": {
    "_id": "660e8400-e29b-41d4-a716-446655440001",
    "watchlistName": "Real Time Alerts",
    "category": null,
    "isin": []
  }
}
```

---
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

## Corporate Filings

### Get Corporate Filings

```bash
# Basic request
curl -X GET http://localhost:5001/api/corporate_filings
```

---

# With filters
curl -X GET "http://localhost:5001/api/corporate_filings?start_date=2025-01-01&end_date=2025-10-16&category=Financial%20Results&symbol=RELIANCE&isin=INE002A01018"
```

**Query Parameters:**
- `start_date` (optional): Start date in YYYY-MM-DD format
- `end_date` (optional): End date in YYYY-MM-DD format  
- `category` (optional): Comma-separated list of categories
- `symbol` (optional): Comma-separated list of stock symbols
- `isin` (optional): Comma-separated list of ISINs

**Response:**
```json
{
  "count": 2,
  "filings": [
    {
      "corp_id": "880e8400-e29b-41d4-a716-446655440003",
      "securityid": "12345",
      "summary": "Reliance Industries announces Q2 FY2025 financial results",
      "fileurl": "https://example.com/filing.pdf",
      "date": "2025-10-15T09:30:00.000Z",
      "ai_summary": "**Category:** Financial Results\n**Headline:** Q2 Results\n\nReliance Industries reports strong Q2 performance with 15% revenue growth.",
      "category": "Financial Results",
      "isin": "INE002A01018",
      "companyname": "Reliance Industries Limited",
      "symbol": "RELIANCE",
      "headline": "Q2 FY2025 Financial Results",
      "sentiment": "positive",
      "investorCorp": [
        {
          "id": "990e8400-e29b-41d4-a716-446655440004",
          "investor_id": "INV001",
          "investor_name": "John Doe",
          "aliasBool": false,
          "aliasName": null,
          "verified": true,
          "type": "individual",
          "alias_id": null
        }
      ]
    }
  ]
}
```

### Get Filing by ID

```bash
curl -X GET http://localhost:5001/api/corporate_filings/880e8400-e29b-41d4-a716-446655440003
```

**Response:**
```json
{
  "corp_id": "880e8400-e29b-41d4-a716-446655440003",
  "securityid": "12345",
  "summary": "Reliance Industries announces Q2 FY2025 financial results",
  "fileurl": "https://example.com/filing.pdf",
  "date": "2025-10-15T09:30:00.000Z",
  "ai_summary": "**Category:** Financial Results\n**Headline:** Q2 Results\n\nReliance Industries reports strong Q2 performance with 15% revenue growth.",
  "category": "Financial Results",
  "isin": "INE002A01018",
  "companyname": "Reliance Industries Limited",
  "symbol": "RELIANCE",
  "headline": "Q2 FY2025 Financial Results",
  "sentiment": "positive"
}
```

---

## Stock Price Data

### Get Stock Price Data

```bash
# Get all available data
curl -X GET "http://localhost:5001/api/stock_price?isin=INE002A01018" \
  -H "Authorization: Bearer <your_access_token>"

# Get data for specific time range
curl -X GET "http://localhost:5001/api/stock_price?isin=INE002A01018&range=1m" \
  -H "Authorization: Bearer <your_access_token>"
```

**Query Parameters:**
- `isin` (required): ISIN code of the security
- `range` (optional): Time range - `1w`, `1m`, `3m`, `6m`, `1y`, `max` (default: `max`)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "close": 2450.75,
      "date": "2025-10-16"
    },
    {
      "close": 2435.20,
      "date": "2025-10-15"
    }
  ],
  "metadata": {
    "isin": "INE002A01018",
    "range": "1m",
    "total_records": 2
  }
}
```

---

## Saved Announcements

The Saved Announcements feature allows users to bookmark important financial announcements and track their price performance over time. This section provides full CRUD (Create, Read, Update, Delete) operations for managing saved announcements.

**Available Operations:**
- **Create**: Save new announcements with automatic price tracking
- **Read**: Fetch saved announcements with current vs saved price comparisons
- **Update**: Modify notes and annotations for saved items
- **Delete**: Remove saved announcements from your collection

### Save Announcement

```bash
curl -X POST http://localhost:5001/api/save_announcement \
  -H "Authorization: Bearer <your_access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "item_type": "ANNOUNCEMENT",
    "item_id": "880e8400-e29b-41d4-a716-446655440003",
    "isin": "INE002A01018",
    "note": "Interesting quarterly results to monitor"
  }'
```

**Valid Item Types:**
- `ANNOUNCEMENT`
- `FINANCIAL_RESULT`
- `CONCALL_TRANSCRIPT`
- `ANNUAL_REPORT`
- `INVESTOR_PRESENTATION`
- `LARGE_DEAL`

**Response:**
```json
{
  "message": "Item saved successfully",
  "status": "success",
  "data": {
    "saved_item": {
      "id": "aa0e8400-e29b-41d4-a716-446655440005",
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "item_type": "ANNOUNCEMENT",
      "related_announcement_id": "880e8400-e29b-41d4-a716-446655440003",
      "note": "Interesting quarterly results to monitor",
      "saved_price": "2450.75",
      "saved_at": "2025-10-16T10:30:00.000Z"
    },
    "stock_price": "2450.75"
  }
}
```

### Fetch Saved Announcements

```bash
curl -X GET http://localhost:5001/api/fetch_saved_announcements \
  -H "Authorization: Bearer <your_access_token>"
```

**Response:**
```json
{
  "message": "Saved announcements fetched successfully",
  "status": "success",
  "data": [
    {
      "saved_item_id": "aa0e8400-e29b-41d4-a716-446655440005",
      "item_type": "ANNOUNCEMENT",
      "note": "Interesting quarterly results to monitor",
      "saved_at": "2025-10-16T10:30:00.000Z",
      "saved_price": "2450.75",
      "related_announcement_id": "880e8400-e29b-41d4-a716-446655440003",
      "related_deal_id": null,
      "corp_id": "880e8400-e29b-41d4-a716-446655440003",
      "summary": "Reliance Industries announces Q2 FY2025 financial results",
      "isin": "INE002A01018",
      "companyname": "Reliance Industries Limited",
      "symbol": "RELIANCE",
      "category": "Financial Results",
      "current_price": 2475.30,
      "percentage_change": 1.00,
      "absolute_change": 24.55,
      "price_calculation_time": "2025-10-16T11:00:00.000Z"
    }
  ]
}
```

### Update Saved Announcement Note

```bash
curl -X PUT http://localhost:5001/api/update_saved_announcement/aa0e8400-e29b-41d4-a716-446655440005 \
  -H "Authorization: Bearer <your_access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "Updated note: Strong performance this quarter"
  }'
```

**Response:**
```json
{
  "message": "Note updated successfully",
  "status": "success",
  "data": {
    "saved_item_id": "aa0e8400-e29b-41d4-a716-446655440005",
    "old_note": "Interesting quarterly results to monitor",
    "new_note": "Updated note: Strong performance this quarter",
    "updated_at": "2025-10-16T11:15:00.000Z"
  }
}
```

### Delete Saved Announcement

```bash
curl -X DELETE http://localhost:5001/api/delete_saved_announcement/aa0e8400-e29b-41d4-a716-446655440005 \
  -H "Authorization: Bearer <your_access_token>"
```

**Response:**
```json
{
  "message": "Saved announcement deleted successfully",
  "status": "success",
  "data": {
    "deleted_item_id": "aa0e8400-e29b-41d4-a716-446655440005",
    "deleted_item_type": "ANNOUNCEMENT",
    "deleted_note": "Updated note: Strong performance this quarter",
    "deleted_at": "2025-10-16T11:30:00.000Z"
  }
}
```

### Calculate Price Difference

```bash
curl -X POST http://localhost:5001/api/calc_price_diff \
  -H "Authorization: Bearer <your_access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "saved_price": "2450.75",
    "isin": "INE002A01018"
  }'
```

**Response:**
```json
{
  "message": "Price difference calculated successfully",
  "status": "success",
  "data": {
    "saved_price": 2450.75,
    "current_price": 2475.30,
    "percentage_change": 1.00,
    "absolute_change": 24.55,
    "calculation_time": "2025-10-16T11:00:00.000Z"
  }
}
```

---

## Company Search

### Search Companies

```bash
curl -X GET "http://localhost:5001/api/company/search?query=reliance"
```

**Response:**
```json
{
  "companies": [
    {
      "company_name": "Reliance Industries Limited",
      "symbol": "RELIANCE",
      "isin": "INE002A01018",
      "sector": "Oil & Gas"
    }
  ]
}
```

---

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "message": "Missing required fields: item_type, item_id, isin",
  "status": "error"
}
```

#### 401 Unauthorized
```json
{
  "message": "Access token is required",
  "status": "error"
}
```

#### 403 Forbidden
```json
{
  "message": "Unauthorized: You can only update your own saved items",
  "status": "error"
}
```

#### 404 Not Found
```json
{
  "message": "Saved item not found",
  "status": "error"
}
```

#### 500 Internal Server Error
```json
{
  "message": "Database service unavailable. Please try again later.",
  "status": "error"
}
```

### Validation Errors

#### Invalid ISIN Format
```json
{
  "message": "Invalid ISIN format. ISIN must be a 12-character alphanumeric code.",
  "status": "error"
}
```

#### Invalid Date Format
```json
{
  "message": "Invalid start_date format. Use YYYY-MM-DD",
  "status": "error"
}
```

#### Invalid Item Type
```json
{
  "message": "Invalid item_type. Must be one of: ['ANNOUNCEMENT', 'FINANCIAL_RESULT', 'CONCALL_TRANSCRIPT', 'ANNUAL_REPORT', 'INVESTOR_PRESENTATION', 'LARGE_DEAL']",
  "status": "error"
}
```

---

## Rate Limiting

The API implements standard rate limiting practices. Please be mindful of request frequency to ensure optimal performance for all users.

## Support

For technical support or questions about the API, please contact the development team or check the project documentation.

---

## Environment Variables

Make sure the following environment variables are set:

```bash
SUPABASE_URL2=your_supabase_url
SUPABASE_KEY2=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
PASSWORD_SALT=your_password_salt
DEBUG_MODE=false
PORT=5001
```

## Socket.IO Support

The API also includes Socket.IO support for real-time features. Connect to the WebSocket endpoint for live updates on announcements and price changes.

### WebSocket Connection
```javascript
const socket = io('http://localhost:5001');

// Join the global room for announcements
socket.emit('join', { room: 'all' });

// Listen for new announcements
socket.on('new_announcement', (data) => {
  console.log('New announcement:', data);
});
```