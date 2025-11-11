#!/bin/bash

# Admin Server Startup Script
echo "🚀 Starting Admin Verification Server..."

# Change to admin_server directory
cd /Users/anshulkumar/backfin/admin_server

# Activate virtual environment (if using one)
# source ../venv/bin/activate

# Set environment variables
export PYTHONPATH="/Users/anshulkumar/backfin/admin_server:$PYTHONPATH"
export ADMIN_SERVER_PORT=9000
export ADMIN_SERVER_HOST=0.0.0.0

# Redis configuration (local testing)
export REDIS_URL=redis://localhost:6379
export REDIS_HOST=localhost
export REDIS_PORT=6379

# Start the admin server
echo "📍 Admin Dashboard will be available at: http://localhost:9000/admin/dashboard"
echo "🔗 API Base URL: http://localhost:9000"
echo "🛡️ Authentication required - register at: http://localhost:9000/auth/register"

uvicorn main:app --host $ADMIN_SERVER_HOST --port $ADMIN_SERVER_PORT --reload