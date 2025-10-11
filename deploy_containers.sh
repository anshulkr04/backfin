#!/bin/bash

# Containerized Deployment Script
# Everything runs in Docker containers - no local dependencies needed

set -e

echo "🐳 CONTAINERIZED BACKFIN DEPLOYMENT"
echo "===================================="

# Check prerequisites
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker not found. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ Docker Compose not found. Please install Docker Compose first."
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        echo "❌ Docker daemon not running. Please start Docker first."
        exit 1
    fi
    
    echo "✅ Docker and Docker Compose available"
}

# Setup environment
setup_env() {
    if [[ ! -f ".env" ]]; then
        echo "📝 Creating environment file..."
        cat > .env << 'EOF'
# API Keys (UPDATE THESE)
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key
GEMINI_API_KEY=your-gemini-api-key

# Redis Configuration (automatically handled by Docker)
REDIS_HOST=redis
REDIS_PORT=6379

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=INFO
EOF
        echo "⚠️  Please update .env with your actual API keys!"
        echo "   Edit: nano .env"
        read -p "Press Enter after updating .env file..."
    else
        echo "✅ Environment file exists"
    fi
}

# Build and start containers
deploy_containers() {
    echo "🏗️  Building and starting containers..."
    
    # Build all images
    docker-compose -f docker-compose.redis.yml build
    
    # Start services
    docker-compose -f docker-compose.redis.yml up -d
    
    echo "⏳ Waiting for services to be healthy..."
    sleep 10
    
    # Check service health
    echo "🔍 Checking service status..."
    docker-compose -f docker-compose.redis.yml ps
}

# Show system status
show_status() {
    echo ""
    echo "🎉 DEPLOYMENT COMPLETE!"
    echo "======================"
    echo ""
    echo "🌐 Services running:"
    echo "   📊 API Server:     http://localhost:8000"
    echo "   📚 API Docs:       http://localhost:8000/docs"
    echo "   ❤️  Health Check:   http://localhost:8000/health"
    echo "   📈 Queue Status:   http://localhost:8000/queues/status"
    echo "   📊 Monitor:        http://localhost:8080"
    echo ""
    echo "🐳 Docker containers:"
    docker-compose -f docker-compose.redis.yml ps
    echo ""
    echo "💡 Example API call:"
    echo "curl -X POST http://localhost:8000/jobs/announcement \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"company_name\": \"RELIANCE\", \"announcement_text\": \"Q3 earnings released\"}'"
    echo ""
    echo "🔧 Management commands:"
    echo "   View logs:     docker-compose -f docker-compose.redis.yml logs -f"
    echo "   Stop system:   docker-compose -f docker-compose.redis.yml down"
    echo "   Restart:       docker-compose -f docker-compose.redis.yml restart"
    echo "   Update:        git pull && docker-compose -f docker-compose.redis.yml up -d --build"
}

# Main execution
main() {
    check_docker
    setup_env
    deploy_containers
    show_status
}

# Handle cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down containers..."
    docker-compose -f docker-compose.redis.yml down
}

# Set trap for cleanup
trap cleanup EXIT

# Check for help
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Containerized Backfin Deployment"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy    - Deploy all containers (default)"
    echo "  build     - Build images only"
    echo "  start     - Start existing containers"
    echo "  stop      - Stop all containers"
    echo "  restart   - Restart all containers"
    echo "  logs      - Show container logs"
    echo "  status    - Show container status"
    echo "  clean     - Remove all containers and images"
    echo ""
    exit 0
fi

# Handle different commands
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "build")
        check_docker
        docker-compose -f docker-compose.redis.yml build
        ;;
    "start")
        docker-compose -f docker-compose.redis.yml up -d
        show_status
        ;;
    "stop")
        docker-compose -f docker-compose.redis.yml down
        ;;
    "restart")
        docker-compose -f docker-compose.redis.yml restart
        show_status
        ;;
    "logs")
        docker-compose -f docker-compose.redis.yml logs -f
        ;;
    "status")
        docker-compose -f docker-compose.redis.yml ps
        ;;
    "clean")
        docker-compose -f docker-compose.redis.yml down --volumes --remove-orphans
        docker system prune -f
        ;;
    *)
        echo "❌ Unknown command: $1"
        echo "Run $0 --help for usage information"
        exit 1
        ;;
esac