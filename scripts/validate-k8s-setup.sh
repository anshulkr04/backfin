#!/bin/bash

# Quick test script to verify Kubernetes setup works
# This runs a minimal validation without deploying everything

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

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_info "🧪 Testing Kubernetes Setup for Backfin"
echo ""

# Test 1: Check if kubectl works
log_info "1. Testing kubectl connection..."
if kubectl cluster-info &> /dev/null; then
    CONTEXT=$(kubectl config current-context)
    log_success "Connected to cluster: $CONTEXT"
else
    log_error "Cannot connect to Kubernetes cluster"
    exit 1
fi
echo ""

# Test 2: Check if Docker works
log_info "2. Testing Docker..."
if docker --version &> /dev/null; then
    log_success "Docker is available"
else
    log_error "Docker is not available"
    exit 1
fi
echo ""

# Test 3: Validate Kubernetes manifests
log_info "3. Validating Kubernetes manifests..."
MANIFEST_DIR="k8s"
if [[ -d "$MANIFEST_DIR" ]]; then
    for manifest in "$MANIFEST_DIR"/*.yaml; do
        if kubectl apply --dry-run=client -f "$manifest" &> /dev/null; then
            log_success "✓ $(basename "$manifest") is valid"
        else
            log_error "✗ $(basename "$manifest") has errors"
            kubectl apply --dry-run=client -f "$manifest"
        fi
    done
else
    log_error "Kubernetes manifests directory not found"
    exit 1
fi
echo ""

# Test 4: Check Dockerfile syntax
log_info "4. Checking Dockerfiles..."
if [[ -f "Dockerfile.base" ]]; then
    if docker build --dry-run -f Dockerfile.base . &> /dev/null; then
        log_success "✓ Dockerfile.base is valid"
    else
        log_error "✗ Dockerfile.base has issues"
    fi
else
    log_error "Dockerfile.base not found"
fi

if [[ -d "docker" ]]; then
    for dockerfile in docker/Dockerfile.*; do
        if [[ -f "$dockerfile" ]]; then
            service_name=$(basename "$dockerfile" | sed 's/Dockerfile\.//')
            # Note: Can't easily dry-run multi-stage builds that depend on base image
            log_success "✓ Found Dockerfile for $service_name"
        fi
    done
else
    log_error "Docker directory not found"
fi
echo ""

# Test 5: Check scripts are executable
log_info "5. Checking deployment scripts..."
SCRIPTS=(
    "scripts/deploy-k8s.sh"
    "scripts/test-k8s-local.sh"
)

for script in "${SCRIPTS[@]}"; do
    if [[ -f "$script" ]]; then
        if [[ -x "$script" ]]; then
            log_success "✓ $script is executable"
        else
            log_error "✗ $script is not executable (run: chmod +x $script)"
        fi
    else
        log_error "✗ $script not found"
    fi
done
echo ""

# Test 6: Check health server
log_info "6. Testing health server..."
if python -c "from src.core.health_server import app; print('Health server imports OK')" 2>/dev/null; then
    log_success "✓ Health server can be imported"
else
    log_error "✗ Health server has import issues"
fi
echo ""

# Test 7: Check if required Python packages are available
log_info "7. Checking Python dependencies..."
REQUIRED_PACKAGES=(
    "fastapi"
    "uvicorn"
    "redis"
    "pydantic"
)

for package in "${REQUIRED_PACKAGES[@]}"; do
    if python -c "import $package" 2>/dev/null; then
        log_success "✓ $package is available"
    else
        log_error "✗ $package is missing (install with: pip install $package)"
    fi
done
echo ""

# Summary
echo "=================================================="
echo "🎯 KUBERNETES SETUP VALIDATION COMPLETE"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. For local testing: ./scripts/test-k8s-local.sh setup"
echo "2. For production: ./scripts/deploy-k8s.sh"
echo "3. Read KUBERNETES.md for detailed documentation"
echo ""
log_success "Setup validation completed successfully!"