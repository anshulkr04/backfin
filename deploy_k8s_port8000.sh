#!/bin/bash

# Kubernetes Deployment for Port 8000 Setup
# This deploys Backfin to Kubernetes with API accessible on port 8000

set -e

echo "🚀 KUBERNETES DEPLOYMENT - PORT 8000"
echo "===================================="

# Configuration
NAMESPACE="backfin"
API_PORT="8000"
MONITOR_PORT="8081"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_k8s() {
    log_info "Checking Kubernetes prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl first."
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Check your kubeconfig."
        log_info "To set up a local cluster:"
        log_info "  minikube start"
        log_info "  # or"
        log_info "  kind create cluster"
        exit 1
    fi
    
    log_success "Kubernetes cluster accessible"
}

# Setup environment file
setup_k8s_env() {
    log_info "Setting up Kubernetes environment..."
    
    if [[ ! -f ".env" ]]; then
        log_warning "No .env file found. Creating template..."
        cat > .env << 'EOF'
# API Keys (UPDATE THESE)
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key
GEMINI_API_KEY=your-gemini-api-key

# Redis Configuration
REDIS_HOST=redis-service
REDIS_PORT=6379

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=INFO
EOF
        log_error "Please update .env with your actual API keys!"
        read -p "Press Enter after updating .env file..."
    fi
    
    # Create Kubernetes secrets from .env
    log_info "Creating Kubernetes secrets..."
    source .env
    
    # Delete existing secrets if they exist
    kubectl delete secret backfin-secrets -n $NAMESPACE --ignore-not-found=true
    
    # Create new secrets
    kubectl create secret generic backfin-secrets \
        --from-literal=SUPABASE_URL="${SUPABASE_URL}" \
        --from-literal=SUPABASE_KEY="${SUPABASE_KEY}" \
        --from-literal=GEMINI_API_KEY="${GEMINI_API_KEY}" \
        -n $NAMESPACE
    
    log_success "Kubernetes secrets created"
}

# Build Docker images
build_images() {
    log_info "Building Docker images for Kubernetes..."
    
    # Build API image
    log_info "Building API server image..."
    docker build -t backfin/api-server:latest -f docker/Dockerfile.api .
    
    # Build worker spawner image
    log_info "Building worker spawner image..."
    docker build -t backfin/worker-spawner:latest -f docker/Dockerfile.worker-spawner .
    
    # Build scraper image
    log_info "Building scraper image..."
    docker build -t backfin/scraper:latest -f docker/Dockerfile.scraper .
    
    # Build monitor image
    log_info "Building monitor image..."
    docker build -t backfin/monitor:latest -f docker/Dockerfile.monitor .
    
    # Build database cleaner image
    log_info "Building database cleaner image..."
    docker build -t backfin/db-cleaner:latest -f docker/Dockerfile.db-cleaner .
    
    log_success "All Docker images built"
}

# Load images to Kubernetes (for local clusters)
load_images_k8s() {
    # Check if we're using minikube
    if kubectl config current-context | grep -q minikube; then
        log_info "Loading images to minikube..."
        minikube image load backfin/api-server:latest
        minikube image load backfin/worker-spawner:latest
        minikube image load backfin/scraper:latest
        minikube image load backfin/monitor:latest
        minikube image load backfin/db-cleaner:latest
        log_success "Images loaded to minikube"
    elif kubectl config current-context | grep -q kind; then
        log_info "Loading images to kind..."
        kind load docker-image backfin/api-server:latest
        kind load docker-image backfin/worker-spawner:latest
        kind load docker-image backfin/scraper:latest
        kind load docker-image backfin/monitor:latest
        log_success "Images loaded to kind"
    else
        log_warning "Not using local cluster - assuming images are in registry"
    fi
}

# Deploy to Kubernetes
deploy_k8s() {
    log_info "Deploying to Kubernetes..."
    
    # Apply manifests in order
    log_info "Creating namespace..."
    kubectl apply -f k8s/namespace.yaml
    
    log_info "Setting up secrets..."
    setup_k8s_env
    
    log_info "Deploying Redis..."
    kubectl apply -f k8s/redis.yaml
    
    log_info "Deploying API server..."
    kubectl apply -f k8s/api.yaml
    
    log_info "Deploying workers..."
    kubectl apply -f k8s/workers.yaml
    
    log_info "Deploying scrapers..."
    kubectl apply -f k8s/scrapers.yaml
    
    log_info "Setting up cronjobs..."
    kubectl apply -f k8s/cronjobs.yaml
    
    log_info "Applying policies..."
    kubectl apply -f k8s/policies.yaml
    
    log_success "All manifests applied"
}

# Wait for deployment
wait_for_deployment() {
    log_info "Waiting for deployments to be ready..."
    
    # Wait for API server
    kubectl wait --for=condition=available --timeout=300s deployment/api-server -n $NAMESPACE
    
    # Wait for Redis
    kubectl wait --for=condition=available --timeout=300s deployment/redis -n $NAMESPACE
    
    log_success "Core services are ready"
}

# Setup port forwarding for port 8000
setup_port_forward() {
    log_info "Setting up port forwarding to port 8000..."
    
    # Kill any existing port forwards
    pkill -f "kubectl.*port-forward.*8000" || true
    pkill -f "kubectl.*port-forward.*8081" || true
    
    # Start port forwarding in background
    nohup kubectl port-forward svc/api-service 8000:8000 -n $NAMESPACE > /dev/null 2>&1 &
    API_PF_PID=$!
    
    # Port forward for monitor (if exists)
    if kubectl get svc queue-manager-service -n $NAMESPACE &> /dev/null; then
        nohup kubectl port-forward svc/queue-manager-service 8081:8080 -n $NAMESPACE > /dev/null 2>&1 &
        MONITOR_PF_PID=$!
    fi
    
    sleep 3
    
    log_success "Port forwarding active (API: 8000, Monitor: 8081)"
    echo "📝 Port forward PIDs: API=$API_PF_PID, Monitor=${MONITOR_PF_PID:-N/A}"
}

# Show status
show_k8s_status() {
    echo ""
    echo "🎉 KUBERNETES DEPLOYMENT COMPLETE!"
    echo "=================================="
    echo ""
    echo "🌐 Services:"
    echo "   📊 API Server:     http://localhost:8000"
    echo "   📚 API Docs:       http://localhost:8000/docs"
    echo "   ❤️  Health Check:   http://localhost:8000/health"
    echo "   📈 Queue Status:   http://localhost:8000/queues/status"
    echo "   📊 Monitor:        http://localhost:8081"
    echo ""
    echo "🔍 Kubernetes Resources:"
    kubectl get all -n $NAMESPACE
    echo ""
    echo "💡 Example API call:"
    echo "curl -X POST http://localhost:8000/jobs/announcement \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"company_name\": \"RELIANCE\", \"announcement_text\": \"Q3 earnings released\"}'"
    echo ""
    echo "🔧 Management commands:"
    echo "   View pods:         kubectl get pods -n $NAMESPACE"
    echo "   View logs:         kubectl logs -f deployment/api-server -n $NAMESPACE"
    echo "   Scale API:         kubectl scale deployment api-server --replicas=3 -n $NAMESPACE"
    echo "   Delete all:        kubectl delete namespace $NAMESPACE"
    echo ""
    echo "⚠️  Note: Port forwarding is active. Keep this terminal open or run:"
    echo "   kubectl port-forward svc/api-service 8000:8000 -n $NAMESPACE"
}

# Main execution
main() {
    check_k8s
    build_images
    load_images_k8s
    deploy_k8s
    wait_for_deployment
    setup_port_forward
    show_k8s_status
}

# Handle commands
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "build")
        build_images
        ;;
    "status")
        kubectl get all -n $NAMESPACE
        ;;
    "logs")
        kubectl logs -f deployment/api-server -n $NAMESPACE
        ;;
    "port-forward")
        setup_port_forward
        echo "✅ Port forwarding active"
        echo "   API: http://localhost:8000"
        echo "   Monitor: http://localhost:8081"
        echo ""
        echo "⏹️  Press Ctrl+C to stop"
        wait
        ;;
    "clean")
        log_info "Cleaning up Kubernetes deployment..."
        kubectl delete namespace $NAMESPACE --ignore-not-found=true
        pkill -f "kubectl.*port-forward" || true
        log_success "Cleanup complete"
        ;;
    "help")
        echo "Kubernetes Deployment for Port 8000"
        echo ""
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  deploy        - Full deployment (default)"
        echo "  build         - Build Docker images only"
        echo "  status        - Show Kubernetes status"
        echo "  logs          - Show API server logs"
        echo "  port-forward  - Setup port forwarding only"
        echo "  clean         - Delete all resources"
        echo ""
        ;;
    *)
        log_error "Unknown command: $1"
        echo "Run $0 help for usage information"
        exit 1
        ;;
esac