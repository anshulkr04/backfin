#!/bin/bash

# Quick Setup Script for VM Deployment
# Run this after cloning the repository

set -e

echo "🚀 BACKFIN QUICK SETUP"
echo "====================="

# Check if we're in the right directory
if [[ ! -f "start_system.py" ]]; then
    echo "❌ Error: Run this script from the backfin project root directory"
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.8+ first."
    exit 1
fi

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "⚠️  Docker not found. Installing basic packages only."
    echo "   To use Redis, install Docker and run: docker run -d --name backfin-redis -p 6379:6379 redis:7-alpine"
fi

# Step 1: Create virtual environment
echo "📦 Setting up Python environment..."
if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
fi

source .venv/bin/activate

# Step 2: Install dependencies
echo "📚 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Step 3: Create environment file
echo "⚙️  Setting up environment..."
if [[ ! -f ".env" ]]; then
    cat > .env << 'EOF'
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# API Configuration  
API_HOST=0.0.0.0
API_PORT=8000

# API Keys (UPDATE THESE)
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key
GEMINI_API_KEY=your-gemini-api-key

# Logging
LOG_LEVEL=INFO
EOF
    echo "📝 Created .env file - please update with your API keys"
else
    echo "✅ Environment file already exists"
fi

# Step 4: Start Redis if Docker is available
if command -v docker &> /dev/null; then
    echo "🔧 Starting Redis..."
    
    # Check if Redis container exists
    if docker ps -a --filter name=backfin-redis --format '{{.Names}}' | grep -q backfin-redis; then
        docker start backfin-redis
    else
        docker run -d --name backfin-redis -p 6379:6379 redis:7-alpine
    fi
    
    echo "✅ Redis started on port 6379"
else
    echo "⚠️  Please start Redis manually or install Docker"
fi

# Step 5: Test the setup
echo "🧪 Testing system..."
python -c "
import redis, fastapi, uvicorn
print('✅ All required packages installed')

try:
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    r.ping()
    print('✅ Redis connection successful')
except:
    print('⚠️  Redis not accessible - will start with system startup')
"

# Make scripts executable
chmod +x start_system.py

echo ""
echo "🎉 SETUP COMPLETE!"
echo "=================="
echo ""
echo "🚀 To start the system:"
echo "   python start_system.py"
echo ""
echo "🌐 Once running:"
echo "   API Docs: http://localhost:8000/docs"
echo "   Health Check: http://localhost:8000/health"
echo "   Queue Status: http://localhost:8000/queues/status"
echo ""
echo "💡 Example API call:"
echo "curl -X POST http://localhost:8000/jobs/announcement \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"company_name\": \"RELIANCE\", \"announcement_text\": \"Q3 earnings released\"}'"
echo ""
echo "📝 Don't forget to update .env with your actual API keys!"