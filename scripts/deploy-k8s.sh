#!/bin/bash

# Backfin Kubernetes Deployment Script
# This script builds Docker images and deploys the entire Backfin system to Kubernetes

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="backfin"
DOCKER_REGISTRY="backfin"  # Change this to your registry
VERSION=${1:-"latest"}
CONTEXT=${2:-$(kubectl config current-context)}

# Functions
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

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed. Please install kubectl first."
        exit 1
    fi
    
    # Check if docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if cluster is accessible
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Check your kubeconfig."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

build_base_image() {
    log_info "Building base Docker image..."
    docker build -t ${DOCKER_REGISTRY}/base:${VERSION} -f Dockerfile.base .
    log_success "Base image built: ${DOCKER_REGISTRY}/base:${VERSION}"
}

build_service_images() {
    log_info "Building service Docker images..."
    
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
        log_info "Building ${service}..."
        docker build -t ${DOCKER_REGISTRY}/${service}:${VERSION} -f docker/Dockerfile.${service} .
        log_success "Built ${DOCKER_REGISTRY}/${service}:${VERSION}"
    done
}

push_images() {
    log_info "Pushing Docker images to registry..."
    
    if [[ "${DOCKER_REGISTRY}" != "backfin" ]]; then
        local images=(
            "base"
            "bse-scraper"
            "nse-scraper"
            "ai-worker" 
            "supabase-worker"
            "investor-worker"
            "api-server"
            "queue-manager"
        )
        
        for image in "${images[@]}"; do
            log_info "Pushing ${DOCKER_REGISTRY}/${image}:${VERSION}..."
            docker push ${DOCKER_REGISTRY}/${image}:${VERSION}
        done
        log_success "All images pushed to registry"
    else
        log_warning "Using local registry 'backfin' - skipping push"
    fi
}

create_secrets() {
    log_info "Setting up secrets..."
    
    # Check if secrets file exists
    if [[ ! -f ".env" ]]; then
        log_warning "No .env file found. Please create one with your secrets:"
        echo "SUPABASE_URL=your-supabase-url"
        echo "SUPABASE_KEY=your-supabase-key" 
        echo "GEMINI_API_KEY=your-gemini-api-key"
        echo "REDIS_PASSWORD=your-redis-password"
        echo ""
        log_warning "Update k8s/secrets.yaml with base64 encoded values"
        return
    fi
    
    # Source environment variables
    source .env
    
    # Create base64 encoded secrets
    SUPABASE_URL_B64=$(echo -n "${SUPABASE_URL}" | base64)
    SUPABASE_KEY_B64=$(echo -n "${SUPABASE_KEY}" | base64)
    GEMINI_API_KEY_B64=$(echo -n "${GEMINI_API_KEY}" | base64)
    REDIS_PASSWORD_B64=$(echo -n "${REDIS_PASSWORD:-}" | base64)
    
    # Update secrets file
    sed -i.bak "s|SUPABASE_URL: \"\"|SUPABASE_URL: \"${SUPABASE_URL_B64}\"|g" k8s/secrets.yaml
    sed -i.bak "s|SUPABASE_KEY: \"\"|SUPABASE_KEY: \"${SUPABASE_KEY_B64}\"|g" k8s/secrets.yaml  
    sed -i.bak "s|GEMINI_API_KEY: \"\"|GEMINI_API_KEY: \"${GEMINI_API_KEY_B64}\"|g" k8s/secrets.yaml
    sed -i.bak "s|REDIS_PASSWORD: \"\"|REDIS_PASSWORD: \"${REDIS_PASSWORD_B64}\"|g" k8s/secrets.yaml
    
    log_success "Secrets configured"
}

deploy_to_kubernetes() {
    log_info "Deploying to Kubernetes cluster: ${CONTEXT}"
    
    # Apply manifests in order
    local manifests=(
        "namespace.yaml"
        "secrets.yaml" 
        "redis.yaml"
        "scrapers.yaml"
        "workers.yaml"
        "api.yaml"
        "cronjobs.yaml"
        "policies.yaml"
    )
    
    for manifest in "${manifests[@]}"; do
        log_info "Applying ${manifest}..."
        kubectl apply -f k8s/${manifest}
    done
    
    log_success "All manifests applied"
}

wait_for_deployment() {
    log_info "Waiting for deployments to be ready..."
    
    local deployments=(
        "redis"
        "bse-scraper"
        "nse-scraper"
        "ai-worker"
        "supabase-worker"
        "investor-worker"
        "api-server"
        "queue-manager"
    )
    
    for deployment in "${deployments[@]}"; do
        log_info "Waiting for ${deployment} deployment..."
        kubectl wait --for=condition=available --timeout=300s deployment/${deployment} -n ${NAMESPACE}
    done
    
    log_success "All deployments are ready"
}

check_deployment_status() {
    log_info "Checking deployment status..."
    
    echo ""
    echo "=== PODS ==="
    kubectl get pods -n ${NAMESPACE}
    
    echo ""
    echo "=== SERVICES ==="
    kubectl get services -n ${NAMESPACE}
    
    echo ""
    echo "=== DEPLOYMENTS ==="
    kubectl get deployments -n ${NAMESPACE}
    
    echo ""
    echo "=== CRONJOBS ==="
    kubectl get cronjobs -n ${NAMESPACE}
}

cleanup() {
    log_info "Cleaning up..."
    kubectl delete namespace ${NAMESPACE} --ignore-not-found=true
    log_success "Cleanup completed"
}

show_help() {
    echo "Backfin Kubernetes Deployment Script"
    echo ""
    echo "Usage: $0 [VERSION] [CONTEXT] [COMMAND]"
    echo ""
    echo "VERSION: Docker image version tag (default: latest)"
    echo "CONTEXT: Kubernetes context (default: current context)"
    echo ""
    echo "Commands:"
    echo "  deploy    - Full deployment (default)"
    echo "  build     - Build Docker images only"
    echo "  push      - Push images to registry"
    echo "  apply     - Apply Kubernetes manifests only"
    echo "  status    - Check deployment status"
    echo "  cleanup   - Delete all resources"
    echo "  help      - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                           # Deploy with latest version"
    echo "  $0 v1.0.0                   # Deploy with specific version"
    echo "  $0 latest minikube deploy    # Deploy to minikube"
    echo "  $0 latest '' build           # Build images only"
}

# Main execution
main() {
    local command=${3:-"deploy"}
    
    case "${command}" in
        "deploy")
            check_prerequisites
            build_base_image
            build_service_images
            push_images
            create_secrets
            deploy_to_kubernetes
            wait_for_deployment
            check_deployment_status
            log_success "Deployment completed successfully!"
            ;;
        "build")
            check_prerequisites
            build_base_image
            build_service_images
            log_success "Build completed successfully!"
            ;;
        "push")
            push_images
            log_success "Push completed successfully!"
            ;;
        "apply")
            create_secrets
            deploy_to_kubernetes
            log_success "Apply completed successfully!"
            ;;
        "status")
            check_deployment_status
            ;;
        "cleanup")
            cleanup
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

# Check if help is requested
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    show_help
    exit 0
fi

# Run main function
main "$@"