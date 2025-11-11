#!/bin/bash
# Setup script for the Production-Ready Verification System

set -e

echo "🚀 Setting up Production-Ready Verification System..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
print_status "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

print_success "Prerequisites check passed"

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_status "Creating environment configuration..."
    cat > .env << EOF
# Production Mode (set to FALSE for testing with testdata.json)
PROD=false

# Redis Configuration
REDIS_URL=redis://redis:6379

# Supabase Configuration
SUPABASE_URL=https://zxmsooyaspdpehmicnur.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp4bXNvb3lhc3BkcGVobWljbnVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjI4ODcyNTIsImV4cCI6MjA3ODQ2MzI1Mn0.RLRX4VKHerOkevwmEH5-7FlHiDq6BK5DKKVzeKkef2k

# Admin API Configuration  
ADMIN_JWT_SECRET=admin-super-secret-key-change-in-production-256-bits
ADMIN_API_PORT=8002
ADMIN_SESSION_EXPIRE_HOURS=8
ADMIN_RATE_LIMIT=100

# Test Data Simulation (when PROD=false)
TEST_DATA_INTERVAL=5
TEST_DATA_BATCH_SIZE=1
TEST_DATA_START_DELAY=10

# Queue Management
QUEUE_CLEANUP_INTERVAL=60
QUEUE_TASK_TIMEOUT=1800
QUEUE_SESSION_TIMEOUT=3600
QUEUE_MAX_RETRIES=3

# Logging
LOG_LEVEL=INFO
EOF
    print_success "Created .env file"
else
    print_status ".env file already exists, using existing configuration"
fi

# Build and start services
print_status "Building Docker images..."
docker-compose build

print_status "Starting verification system..."
docker-compose up -d

# Wait for services to be healthy
print_status "Waiting for services to start..."
sleep 15

# Check service health
print_status "Checking service health..."

services=("verif-redis" "verif-admin-api" "verif-queue-manager")
all_healthy=true

for service in "${services[@]}"; do
    if docker-compose ps | grep -q "$service.*Up"; then
        print_success "$service is running"
    else
        print_error "$service is not running"
        all_healthy=false
    fi
done

# Start test simulator if in test mode
PROD_MODE=$(grep "^PROD=" .env | cut -d'=' -f2)
if [ "$PROD_MODE" = "false" ]; then
    print_status "Starting test data simulator..."
    docker-compose --profile testing up -d test-simulator
    
    if docker-compose ps | grep -q "verif-simulator.*Up"; then
        print_success "Test data simulator is running"
    else
        print_warning "Test data simulator failed to start"
    fi
fi

if [ "$all_healthy" = true ]; then
    print_success "All core services are running!"
    echo
    echo "📋 Verification System is ready!"
    echo
    echo "🌐 Services:"
    echo "  • Admin API:      http://localhost:8002"
    echo "  • Admin UI:       http://localhost:8002/ (Basic testing interface)"
    echo "  • Redis UI:       http://localhost:8081 (run: docker-compose --profile debug up -d)"
    echo
    echo "🔧 Management commands:"
    echo "  • View logs:      docker-compose logs -f [service]"
    echo "  • Stop system:    docker-compose down"
    echo "  • Restart:        docker-compose restart [service]"
    echo "  • Start simulator: docker-compose --profile testing up -d"
    echo "  • Debug mode:     docker-compose --profile debug up -d"
    echo
    echo "📖 Quick Start Guide:"
    echo "  1. Open http://localhost:8002 to access the admin interface"
    echo "  2. Register a new admin user"
    echo "  3. Login and create sample tasks for testing"
    echo "  4. Use the WebSocket connection for real-time updates"
    echo
    echo "📊 System Configuration:"
    echo "  • Production Mode: $PROD_MODE"
    if [ "$PROD_MODE" = "false" ]; then
        echo "  • Test Data: Simulator will feed announcements from testdata.json"
        echo "  • Check simulator logs: docker-compose logs -f test-simulator"
    fi
    echo
    echo "🔍 Monitoring:"
    echo "  • API health: curl http://localhost:8002/stats"
    echo "  • System logs: docker-compose logs -f"
    echo
else
    print_error "Some services failed to start. Check logs with: docker-compose logs"
    echo
    echo "🔧 Troubleshooting:"
    echo "  • Check service logs: docker-compose logs [service-name]"
    echo "  • Verify dependencies: docker-compose ps"
    echo "  • Check ports: netstat -tulpn | grep -E ':(6379|8002|8081)'"
    echo "  • Rebuild images: docker-compose build --no-cache"
    exit 1
fi