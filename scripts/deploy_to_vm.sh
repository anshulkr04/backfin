#!/bin/bash

# Quick VM Deployment Script for Backfin Redis Queue Architecture
# Run this script on your VM to deploy the entire system

set -e

# Colors for output
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

# Configuration
DEPLOY_DIR="/opt/backfin"
GITHUB_REPO="https://github.com/anshulkr04/backfin.git"
BRANCH="markback"

echo "🚀 BACKFIN REDIS QUEUE ARCHITECTURE - VM DEPLOYMENT"
echo "=" * 60

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   log_error "Don't run this script as root! Run as regular user with sudo access"
   exit 1
fi

# Step 1: System Prerequisites
log_info "Step 1: Checking system prerequisites..."

# Check OS
if command -v apt &> /dev/null; then
    OS_TYPE="debian"
    log_info "Detected Debian/Ubuntu system"
elif command -v yum &> /dev/null; then
    OS_TYPE="rhel"
    log_info "Detected RHEL/CentOS system"
else
    log_error "Unsupported operating system"
    exit 1
fi

# Update system
log_info "Updating system packages..."
if [[ "$OS_TYPE" == "debian" ]]; then
    sudo apt update && sudo apt upgrade -y
    sudo apt install -y python3 python3-pip python3-venv git docker.io docker-compose curl wget
elif [[ "$OS_TYPE" == "rhel" ]]; then
    sudo yum update -y
    sudo yum install -y python3 python3-pip git docker docker-compose curl wget
fi

# Setup Docker
log_info "Setting up Docker..."
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

log_success "System prerequisites installed"

# Step 2: Setup deployment directory
log_info "Step 2: Setting up deployment directory..."

if [[ -d "$DEPLOY_DIR" ]]; then
    log_warning "Directory $DEPLOY_DIR already exists"
    read -p "Remove existing directory? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo rm -rf "$DEPLOY_DIR"
    else
        log_error "Deployment cancelled"
        exit 1
    fi
fi

sudo mkdir -p "$DEPLOY_DIR"
sudo chown $USER:$USER "$DEPLOY_DIR"

log_success "Deployment directory created: $DEPLOY_DIR"

# Step 3: Clone repository
log_info "Step 3: Cloning repository..."

cd "$DEPLOY_DIR"

if [[ -n "$GITHUB_REPO" ]]; then
    git clone "$GITHUB_REPO" .
    git checkout "$BRANCH"
    log_success "Repository cloned from GitHub"
else
    log_error "Please provide repository URL or transfer files manually"
    log_info "Manual transfer: scp -r /local/path/backfin/ user@vm:/opt/backfin/"
    exit 1
fi

# Step 4: Setup Python environment
log_info "Step 4: Setting up Python virtual environment..."

python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt || log_warning "requirements.txt not found, installing manually"

# Install essential packages
pip install redis pydantic fastapi uvicorn psutil

# Test Python setup
python -c "import redis, pydantic, fastapi; print('✅ Python packages installed')"

log_success "Python environment configured"

# Step 5: Setup Redis
log_info "Step 5: Setting up Redis database..."

# Start Redis with Docker
if [[ -f "docker-compose.redis.yml" ]]; then
    docker-compose -f docker-compose.redis.yml up -d
else
    log_warning "docker-compose.redis.yml not found, creating basic Redis container"
    docker run -d --name backfin-redis -p 6379:6379 redis:7-alpine
fi

# Wait for Redis to start
sleep 5

# Test Redis connection
docker exec -it backfin-redis redis-cli ping || log_error "Redis connection failed"

log_success "Redis database running"

# Step 6: Create environment file
log_info "Step 6: Creating environment configuration..."

if [[ ! -f ".env" ]]; then
    cat > .env << 'EOF'
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# API Keys (UPDATE THESE WITH YOUR ACTUAL VALUES)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
GEMINI_API_KEY=your-gemini-api-key

# Logging
LOG_LEVEL=INFO

# Worker Configuration
WORKER_CONCURRENCY=4
JOB_TIMEOUT=300
EOF

    log_warning "Environment file created. Please update .env with your actual API keys!"
    log_info "Edit with: nano $DEPLOY_DIR/.env"
else
    log_success "Environment file already exists"
fi

# Step 7: Test the system
log_info "Step 7: Testing system components..."

# Test Redis queue system
if python scripts/test_queue_system.py; then
    log_success "Redis queue system working"
else
    log_error "Redis queue system test failed"
    exit 1
fi

# Test structure
if python scripts/test_structure.py; then
    log_success "System structure validated"
else
    log_warning "Some structure tests failed - check imports"
fi

# Step 8: Setup systemd service
log_info "Step 8: Setting up system service..."

sudo tee /etc/systemd/system/backfin-spawner.service << EOF
[Unit]
Description=Backfin Worker Spawner
After=network.target docker.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$DEPLOY_DIR
Environment=PATH=$DEPLOY_DIR/.venv/bin
ExecStart=$DEPLOY_DIR/.venv/bin/python management/worker_spawner.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable backfin-spawner

log_success "Systemd service configured"

# Step 9: Create monitoring script
log_info "Step 9: Creating monitoring tools..."

cat > monitor.sh << 'EOF'
#!/bin/bash
cd /opt/backfin
source .venv/bin/activate

echo "=== Backfin System Status - $(date) ==="
echo

echo "=== Redis Status ==="
docker ps | grep redis || echo "❌ Redis not running"

echo
echo "=== Worker Spawner Status ==="
if systemctl is-active --quiet backfin-spawner; then
    echo "✅ Worker spawner service running"
    ps aux | grep worker_spawner | grep -v grep | head -1
else
    echo "❌ Worker spawner service not running"
fi

echo
echo "=== Queue Status ==="
python -c "
import redis
try:
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    queues = ['backfin:queue:new_announcements', 'backfin:queue:ai_processing', 'backfin:queue:supabase_upload', 'backfin:queue:investor_processing']
    total_jobs = 0
    for q in queues:
        length = r.llen(q)
        total_jobs += length
        status = '🔴' if length > 0 else '🟢'
        print(f'{status} {q.split(\":\")[-1].upper()}: {length} jobs')
    print(f'\\n📊 Total jobs in system: {total_jobs}')
    
    info = r.info()
    memory_mb = info.get('used_memory', 0) / (1024 * 1024)
    print(f'💾 Redis memory: {memory_mb:.2f} MB')
    print(f'👥 Connected clients: {info.get(\"connected_clients\", 0)}')
except Exception as e:
    print(f'❌ Redis connection error: {e}')
"
EOF

chmod +x monitor.sh

log_success "Monitoring script created: ./monitor.sh"

# Step 10: Final setup
log_info "Step 10: Final configuration..."

# Create logs directory
mkdir -p logs

# Create backup directory
mkdir -p backups

# Set proper permissions
chmod +x workers/ephemeral_*.py management/worker_spawner.py scripts/*.py

log_success "Permissions set correctly"

# Deployment complete
echo
echo "🎉 DEPLOYMENT COMPLETE!"
echo "=" * 60
log_success "Backfin Redis Queue Architecture deployed successfully!"

echo
echo "📋 NEXT STEPS:"
echo "1. Update API keys in .env file:"
echo "   nano $DEPLOY_DIR/.env"
echo
echo "2. Start the worker spawner service:"
echo "   sudo systemctl start backfin-spawner"
echo
echo "3. Check system status:"
echo "   $DEPLOY_DIR/monitor.sh"
echo
echo "4. Test with a job:"
echo "   cd $DEPLOY_DIR && source .venv/bin/activate"
echo "   python scripts/test_ephemeral_workers.py"
echo
echo "5. Monitor live system:"
echo "   python scripts/live_monitor.py"
echo

echo "🔧 INTEGRATION WITH YOUR BACKEND (PORT 8000):"
echo "Add this to your existing backend code:"
echo
echo "import redis"
echo "redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)"
echo "# Then add jobs: redis_client.lpush('backfin:queue:ai_processing', job_json)"
echo

echo "📊 SYSTEM ACCESS:"
echo "- Redis: localhost:6379"
echo "- Your Backend: localhost:8000 (unchanged)"
echo "- System Monitor: $DEPLOY_DIR/monitor.sh"
echo "- Logs: systemctl status backfin-spawner"

echo
log_success "Ready for production! 🚀"