#!/bin/bash

# Backfin Verification System Startup Script

echo "🚀 Starting Backfin Verification System..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "📝 Please copy .env.example to .env and fill in your values"
    echo "   cp .env.example .env"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Run application
echo "✨ Starting application on http://0.0.0.0:5002"
echo "📖 API documentation: http://localhost:5002/docs"
echo ""
python app.py
