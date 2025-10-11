#!/bin/bash

# Local Kubernetes Testing Script for Backfin
# This script helps you test the Kubernetes setup locally using kind or minikube

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# Check if kind is available
check_kind() {
    if command -v kind &> /dev/null; then
        echo "kind"
        return 0
    fi
    return 1
}

# Check if minikube is available
check_minikube() {
    if command -v minikube &> /dev/null; then
        echo "minikube"
        return 0
    fi
    return 1
}

# Setup local cluster
setup_local_cluster() {
    local cluster_type=""
    
    if cluster_type=$(check_kind); then
        log_info "Using kind for local cluster"
        setup_kind_cluster
    elif cluster_type=$(check_minikube); then
        log_info "Using minikube for local cluster"
        setup_minikube_cluster
    else
        log_error "Neither kind nor minikube found. Please install one of them."
        echo "Install kind: https://kind.sigs.k8s.io/docs/user/quick-start/"
        echo "Install minikube: https://minikube.sigs.k8s.io/docs/start/"
        exit 1
    fi
}

setup_kind_cluster() {
    log_info "Creating kind cluster..."
    
    # Create kind config
    cat <<EOF > /tmp/kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
- role: worker
- role: worker
EOF

    # Create cluster if it doesn't exist
    if ! kind get clusters | grep -q "backfin"; then
        kind create cluster --name backfin --config /tmp/kind-config.yaml
    fi
    
    # Set context
    kubectl cluster-info --context kind-backfin
    log_success "Kind cluster ready"
}

setup_minikube_cluster() {
    log_info "Starting minikube cluster..."
    
    # Start minikube if not running
    if ! minikube status &> /dev/null; then
        minikube start --driver=docker --cpus=4 --memory=8192
    fi
    
    # Enable addons
    minikube addons enable ingress
    minikube addons enable metrics-server
    
    log_success "Minikube cluster ready"
}

# Build and load images for local testing
build_and_load_images() {
    log_info "Building and loading Docker images..."
    
    # Build base image
    docker build -t backfin/base:latest -f Dockerfile.base .
    
    # Build service images
    local services=(
        "bse-scraper"
        "nse-scraper"
        "ai-worker"
        "supabase-worker"
        "investor-worker"
        "api-server"
        "queue-manager"
    )
    
    for service in "${services[@]}"; do
        docker build -t backfin/${service}:latest -f docker/Dockerfile.${service} .
    done
    
    # Load images into cluster
    if kind get clusters | grep -q "backfin"; then
        log_info "Loading images into kind cluster..."
        docker tag backfin/base:latest backfin/base:latest
        kind load docker-image backfin/base:latest --name backfin
        
        for service in "${services[@]}"; do
            kind load docker-image backfin/${service}:latest --name backfin
        done
    elif minikube status &> /dev/null; then
        log_info "Using minikube docker daemon..."
        eval $(minikube docker-env)
        # Images are already built in minikube's docker daemon
    fi
    
    log_success "Images loaded successfully"
}

# Create local environment file
create_local_env() {
    if [[ ! -f ".env.local" ]]; then
        log_info "Creating local environment file..."
        cat <<EOF > .env.local
# Local testing environment variables
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
GEMINI_API_KEY=your-gemini-api-key
REDIS_PASSWORD=
LOG_LEVEL=DEBUG
WORKER_CONCURRENCY=2
EOF
        log_warning "Please update .env.local with your actual credentials"
    fi
}

# Deploy to local cluster
deploy_local() {
    log_info "Deploying to local cluster..."
    
    # Use local environment
    if [[ -f ".env.local" ]]; then
        source .env.local
        
        # Update secrets with local values
        cp k8s/secrets.yaml k8s/secrets.yaml.bak
        
        if [[ -n "${SUPABASE_URL}" ]]; then
            SUPABASE_URL_B64=$(echo -n "${SUPABASE_URL}" | base64)
            sed -i.tmp "s|SUPABASE_URL: \"\"|SUPABASE_URL: \"${SUPABASE_URL_B64}\"|g" k8s/secrets.yaml
        fi
        
        if [[ -n "${SUPABASE_KEY}" ]]; then
            SUPABASE_KEY_B64=$(echo -n "${SUPABASE_KEY}" | base64)
            sed -i.tmp "s|SUPABASE_KEY: \"\"|SUPABASE_KEY: \"${SUPABASE_KEY_B64}\"|g" k8s/secrets.yaml
        fi
        
        if [[ -n "${GEMINI_API_KEY}" ]]; then
            GEMINI_API_KEY_B64=$(echo -n "${GEMINI_API_KEY}" | base64)
            sed -i.tmp "s|GEMINI_API_KEY: \"\"|GEMINI_API_KEY: \"${GEMINI_API_KEY_B64}\"|g" k8s/secrets.yaml
        fi
    fi
    
    # Deploy using main script
    ./scripts/deploy-k8s.sh latest '' apply
    
    log_success "Local deployment completed"
}

# Monitor deployment
monitor_deployment() {
    log_info "Monitoring deployment..."
    
    echo ""
    echo "=== WATCHING PODS ==="
    kubectl get pods -n backfin -w &
    WATCH_PID=$!
    
    sleep 30
    kill $WATCH_PID 2>/dev/null || true
    
    echo ""
    echo "=== FINAL STATUS ==="
    kubectl get all -n backfin
}

# Port forward services for local access
setup_port_forwards() {
    log_info "Setting up port forwards..."
    
    # Port forward API service
    kubectl port-forward service/api-service 8000:80 -n backfin &
    API_PID=$!
    
    # Port forward queue manager
    kubectl port-forward service/queue-manager-service 8080:8080 -n backfin &
    QUEUE_PID=$!
    
    # Port forward Redis (for debugging)
    kubectl port-forward service/redis-service 6379:6379 -n backfin &
    REDIS_PID=$!
    
    echo ""
    log_success "Port forwards active:"
    echo "  API Server: http://localhost:8000"
    echo "  Queue Manager: http://localhost:8080"
    echo "  Redis: localhost:6379"
    echo ""
    echo "Press Ctrl+C to stop port forwards"
    
    # Wait for interrupt
    trap "kill $API_PID $QUEUE_PID $REDIS_PID 2>/dev/null || true" EXIT
    wait
}

# Test the deployment
test_deployment() {
    log_info "Testing deployment..."
    
    # Wait for services to be ready
    kubectl wait --for=condition=available --timeout=300s deployment/api-server -n backfin
    
    # Port forward for testing
    kubectl port-forward service/api-service 8000:80 -n backfin &
    PORT_FORWARD_PID=$!
    
    sleep 5
    
    # Test API health
    if curl -f http://localhost:8000/health &> /dev/null; then
        log_success "API server is healthy"
    else
        log_error "API server health check failed"
    fi
    
    # Test queue manager
    kubectl port-forward service/queue-manager-service 8080:8080 -n backfin &
    QUEUE_PORT_FORWARD_PID=$!
    
    sleep 5
    
    if curl -f http://localhost:8080/health &> /dev/null; then
        log_success "Queue manager is healthy"
    else
        log_error "Queue manager health check failed"
    fi
    
    # Cleanup
    kill $PORT_FORWARD_PID $QUEUE_PORT_FORWARD_PID 2>/dev/null || true
}

# Cleanup local cluster
cleanup_local() {
    log_info "Cleaning up local cluster..."
    
    if kind get clusters | grep -q "backfin"; then
        kind delete cluster --name backfin
    elif minikube status &> /dev/null; then
        minikube delete
    fi
    
    log_success "Local cluster cleaned up"
}

# Show logs
show_logs() {
    local service=${1:-"api-server"}
    kubectl logs -f deployment/${service} -n backfin
}

# Show help
show_help() {
    echo "Backfin Local Kubernetes Testing Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  setup     - Setup local cluster and deploy"
    echo "  deploy    - Deploy to existing cluster"
    echo "  test      - Test the deployment"
    echo "  monitor   - Monitor deployment status"
    echo "  forward   - Setup port forwards"
    echo "  logs      - Show logs (default: api-server)"
    echo "  cleanup   - Delete local cluster"
    echo "  help      - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 setup             # Full local setup"
    echo "  $0 logs ai-worker    # Show AI worker logs"
    echo "  $0 forward           # Port forward services"
}

# Main execution
main() {
    local command=${1:-"setup"}
    
    case "${command}" in
        "setup")
            setup_local_cluster
            create_local_env
            build_and_load_images
            deploy_local
            monitor_deployment
            log_success "Local setup completed! Run '$0 forward' to access services"
            ;;
        "deploy")
            deploy_local
            ;;
        "test")
            test_deployment
            ;;
        "monitor")
            monitor_deployment
            ;;
        "forward")
            setup_port_forwards
            ;;
        "logs")
            show_logs ${2}
            ;;
        "cleanup")
            cleanup_local
            ;;
        "help")
            show_help
            ;;
        *)
            log_error "Unknown command: ${command}"
            show_help
            exit 1
            ;;
    esac
}

if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    show_help
    exit 0
fi

main "$@"