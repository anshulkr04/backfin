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
- **Corporate Filings**: Access corporate announcements and filings
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

The server will start on http://localhost:5001 by default.

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
curl -X POST http://localhost:5001/api/register \
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
curl -X POST http://localhost:5001/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "secure_password"
  }'
```

#### Get User Profile Example
```bash
curl -X GET http://localhost:5001/api/user \
  -H "Authorization: Bearer your_access_token"
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
curl -X GET http://localhost:5001/api/watchlist \
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
curl -X POST http://localhost:5001/api/watchlist \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_access_token" \
  -d '{
    "operation": "create",
    "watchlistName": "Tech Portfolio"
  }'
```

#### Add ISIN to Watchlist Example
```bash
curl -X POST http://localhost:5001/api/watchlist \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_access_token" \
  -d '{
    "operation": "add_isin",
    "watchlist_id": "550e8400-e29b-41d4-a716-446655440000",
    "isin": "US0378331005",
    "category": "Technology"
  }'
```

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
| `category` | String | No | Optional category to set for the watchlist |

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
curl -X POST http://localhost:5001/api/watchlist/bulk_add \
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
    "category": "Technology"
  }'
```

### JavaScript Example

```javascript
async function bulkAddIsins() {
  const response = await fetch('http://localhost:5001/api/watchlist/bulk_add', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer your_access_token'
    },
    body: JSON.stringify({
      watchlist_id: '550e8400-e29b-41d4-a716-446655440000',
      isins: [
        'US0378331005',
        'US5949181045', 
        'US0231351067',
        'US02079K1079'
      ],
      category: 'Technology'
    })
  });
  
  const data = await response.json();
  console.log(data);
}
```

### Python Example

```python
import requests

def bulk_add_isins(token, watchlist_id, isins, category=None):
    url = 'http://localhost:5001/api/watchlist/bulk_add'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    payload = {
        'watchlist_id': watchlist_id,
        'isins': isins
    }
    
    if category:
        payload['category'] = category
        
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

# Example usage
token = 'your_access_token'
watchlist_id = '550e8400-e29b-41d4-a716-446655440000'
isins = [
    'US0378331005',
    'US5949181045',
    'US0231351067',
    'US02079K1079'
]
result = bulk_add_isins(token, watchlist_id, isins, 'Technology')
print(result)
```

## Implementation Details

1. Each ISIN is validated for format (12-character alphanumeric)
2. Duplicate ISINs (already in the watchlist) are skipped
3. Each ISIN is inserted as a separate row in the `watchlistdata` table
4. If provided, the category is set for the watchlist
5. The response includes detailed information about successful, duplicate, and failed ISINs

### Corporate Filings

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/corporate_filings` | GET | Get corporate filings with filters | Yes |
| `/api/corporate_filings/<corp_id>` | GET | Get specific filing by ID | No |
| `/api/test_corporate_filings` | GET | Get test corporate filings | No |

#### Get Corporate Filings Example
```bash
curl -X GET "http://localhost:5001/api/corporate_filings?start_date=2025-01-01&end_date=2025-05-20&category=Financial%20Results&symbol=AAPL" \
  -H "Authorization: Bearer your_access_token"
```

#### Response
```json
{
  "count": 3,
  "filings": [
    {
      "id": "filing-123",
      "symbol": "AAPL",
      "isin": "US0378331005",
      "category": "Financial Results",
      "summary": "Apple Inc. announces financial results for Q1 2025",
      "ai_summary": "**Category:** Financial Results\n**Headline:** Q1 2025 Results\n\nApple Inc. announces financial results for Q1 2025 with a 12% increase in revenue.",
      "date": "2025-04-28T14:30:00.000Z",
      "companyname": "Apple Inc.",
      "corp_id": "corp-123",
      "headline": "Apple Inc. announces financial results for Q1 2025 with a growth of 20%",
      "sentiment": "Positive",
    }
  ]
}
```

#### Get Filing by ID Example
```bash
curl -X GET http://localhost:5001/api/corporate_filings/corp-123
```

### Company Search

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/company/search` | GET | Search for companies | No |

#### Search Companies Example
```bash
curl -X GET "http://localhost:5001/api/company/search?q=Apple&limit=5"
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
curl -X GET "https://api.example.com/api/stock_price?isin=US0378331005&range=1m" \
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
curl -X POST http://localhost:5001/api/save_announcement \
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
curl -X POST http://localhost:5001/api/save_announcement \
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

## Calculate Price Difference

Calculates the percentage and absolute price difference between a saved price and the current stock price.

#### Calculate Price Difference Example
```bash
curl -X POST http://localhost:5001/api/calc_price_diff \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_access_token" \
  -d '{
    "saved_price": 100.50,
    "isin": "US0378331005"
  }'
```

**Required Fields:**
- `saved_price`: The original saved price (must be a positive number)
- `isin`: International Securities Identification Number

**Response:**
```json
{
  "status": "success",
  "data": {
    "stockDiff": 15.42,
    "percentage_change": 15.42,
    "absolute_change": 15.50,
    "saved_price": 100.50,
    "current_price": 116.00,
    "isin": "US0378331005",
    "calculation_time": "2025-08-05T10:30:00"
  }
}
```

## Authentication

Both endpoints require authentication using Bearer tokens in the Authorization header:
```
Authorization: Bearer your_access_token
```

## Error Responses

All endpoints return consistent error responses:
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
curl -X POST http://localhost:5001/api/insert_new_announcement \
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
curl -X GET http://localhost:5001/api/users
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
curl -X GET http://localhost:5001/api/socket/health
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
curl -X GET http://localhost:5001/api/scraper_status
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
const socket = io('http://localhost:5001');

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
corporatefilings2 Table
- id (Text)
- corp_id (Text)
- Symbol/symbol (Text)
- ISIN/isin (Text)
- Category/category (Text)
- summary (Text)
- ai_summary (Text)
- date (Timestamp)
- companyname (Text)
- fileurl (Text, Optional)
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

### Debugging

For additional debugging, set `DEBUG_MODE=true` and check the server logs for detailed information about requests, responses, and errors.

---

For additional help, please open an issue in the repository or contact the development team.