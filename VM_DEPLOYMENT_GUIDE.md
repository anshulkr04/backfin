# 🚀 VM Deployment Guide - Complete Setup Instructions

## 📋 **Prerequisites Check**

Before starting, ensure your VM has:
- **Python 3.11+** (check: `python3 --version`)
- **Docker** (check: `docker --version`)
- **Git** (check: `git --version`)
- **Port 8000** available for your backend
- **Port 6379** available for Redis
- **At least 2GB RAM** and **5GB disk space**

---

## 🔧 **Step 1: Prepare the VM Environment**

### **1.1 Update System**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL
sudo yum update -y
```

### **1.2 Install Required Packages**
```bash
# Ubuntu/Debian
sudo apt install -y python3 python3-pip python3-venv git docker.io docker-compose curl

# CentOS/RHEL
sudo yum install -y python3 python3-pip git docker docker-compose curl
```

### **1.3 Start Docker Service**
```bash
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker
```

### **1.4 Verify Installation**
```bash
python3 --version     # Should be 3.11+
docker --version      # Should show Docker version
docker-compose --version
```

---

## 📦 **Step 2: Deploy Your Code to VM**

### **2.1 Transfer Code to VM**

**Option A: Git Clone (Recommended)**
```bash
# On your VM
cd /opt  # or wherever you want to deploy
sudo mkdir backfin
sudo chown $USER:$USER backfin
cd backfin

# Clone your repository
git clone https://github.com/anshulkr04/backfin.git .
git checkout markback  # Use your Redis queue branch
```

**Option B: SCP from Local Machine**
```bash
# From your local machine
scp -r /Users/anshulkumar/backfin/ user@your-vm-ip:/opt/backfin/
```

**Option C: Create Archive and Upload**
```bash
# On local machine
cd /Users/anshulkumar
tar -czf backfin.tar.gz backfin/

# Upload to VM
scp backfin.tar.gz user@your-vm-ip:/opt/

# On VM
cd /opt
tar -xzf backfin.tar.gz
cd backfin
```

---

## 🐍 **Step 3: Setup Python Environment**

### **3.1 Create Virtual Environment**
```bash
cd /opt/backfin
python3 -m venv .venv
source .venv/bin/activate

# Verify activation
which python  # Should show /opt/backfin/.venv/bin/python
```

### **3.2 Install Python Dependencies**
```bash
# Install requirements
pip install --upgrade pip
pip install -r requirements.txt

# Install additional packages for queue system
pip install redis pydantic fastapi uvicorn psutil
```

### **3.3 Verify Python Setup**
```bash
python -c "import redis, pydantic, fastapi; print('✅ All packages installed')"
```

---

## 🔧 **Step 4: Setup Redis Database**

### **4.1 Start Redis with Docker**
```bash
cd /opt/backfin

# Start Redis container
docker-compose -f docker-compose.redis.yml up -d

# Verify Redis is running
docker ps | grep redis
docker logs backfin-redis
```

### **4.2 Test Redis Connection**
```bash
# Test from command line
docker exec -it backfin-redis redis-cli ping

# Test from Python
python -c "
import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
r.ping()
print('✅ Redis connection successful')
"
```

---

## ⚙️ **Step 5: Configure Environment Variables**

### **5.1 Create Environment File**
```bash
cd /opt/backfin
cp .env.example .env  # If you have an example file

# Or create new .env file
cat > .env << 'EOF'
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Your API Keys (replace with actual values)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
GEMINI_API_KEY=your-gemini-api-key

# Logging
LOG_LEVEL=INFO

# Worker Configuration
WORKER_CONCURRENCY=4
JOB_TIMEOUT=300
EOF
```

### **5.2 Update with Your Actual Credentials**
```bash
nano .env  # Edit the file with your actual API keys
```

---

## 🧪 **Step 6: Test the System**

### **6.1 Test Core Components**
```bash
cd /opt/backfin
source .venv/bin/activate

# Test Redis queue system
python scripts/test_queue_system.py

# Test structure and imports
python scripts/test_structure.py

# Test complete system
python scripts/test_complete_system.py
```

### **6.2 Verify All Tests Pass**
You should see:
```
✅ All tests passed! Structure is ready.
🎉 Queue system is fully functional!
🎉 ALL TESTS PASSED! System is working correctly!
```

---

## 🚀 **Step 7: Start the Queue System**

### **7.1 Start Worker Spawner (Main Process)**
```bash
cd /opt/backfin
source .venv/bin/activate

# Start ephemeral worker spawner
python management/worker_spawner.py &

# Check it's running
ps aux | grep worker_spawner
```

### **7.2 Start Queue Monitoring (Optional)**
```bash
# In another terminal session
cd /opt/backfin
source .venv/bin/activate

# Start live monitoring
python scripts/live_monitor.py
```

---

## 🔄 **Step 8: Integrate with Your Backend (Port 8000)**

### **8.1 Update Your Backend Code**

Add Redis job creation to your existing backend:

```python
# In your existing backend code (running on port 8000)
import redis
from datetime import datetime
import json
import uuid

# Redis connection
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Function to add announcement to queue
def process_new_announcement(announcement_data):
    job = {
        "job_id": str(uuid.uuid4()),
        "job_type": "ai_processing",
        "corp_id": announcement_data.get('corp_id'),
        "company_name": announcement_data.get('company_name'),
        "security_id": announcement_data.get('security_id'),
        "pdf_url": announcement_data.get('pdf_url'),
        "created_at": datetime.now().isoformat(),
        "priority": "normal",
        "retry_count": 0,
        "max_retries": 3,
        "timeout": 300,
        "metadata": {}
    }
    
    # Add to Redis queue
    redis_client.lpush('backfin:queue:ai_processing', json.dumps(job))
    return job['job_id']

# Example usage in your API endpoint
@app.post("/api/new_announcement")
async def handle_new_announcement(announcement: dict):
    # Your existing logic
    
    # Add to queue for processing
    job_id = process_new_announcement(announcement)
    
    return {"status": "accepted", "job_id": job_id}
```

### **8.2 Update Port Configuration**

If your backend needs different ports:

```bash
# Update docker-compose.redis.yml if needed
nano docker-compose.redis.yml

# Make sure Redis port doesn't conflict with your backend
```

---

## 📊 **Step 9: Setup System Monitoring**

### **9.1 Create Systemd Services (Production)**

Create service files for automatic startup:

```bash
# Worker spawner service
sudo tee /etc/systemd/system/backfin-spawner.service << 'EOF'
[Unit]
Description=Backfin Worker Spawner
After=network.target docker.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/backfin
Environment=PATH=/opt/backfin/.venv/bin
ExecStart=/opt/backfin/.venv/bin/python management/worker_spawner.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable backfin-spawner
sudo systemctl start backfin-spawner
```

### **9.2 Create Monitoring Script**
```bash
# Create monitoring script
cat > /opt/backfin/monitor.sh << 'EOF'
#!/bin/bash
cd /opt/backfin
source .venv/bin/activate

echo "=== Backfin System Status ==="
echo "Date: $(date)"
echo

echo "=== Redis Status ==="
docker ps | grep redis || echo "❌ Redis not running"

echo "=== Worker Spawner Status ==="
ps aux | grep worker_spawner | grep -v grep || echo "❌ Worker spawner not running"

echo "=== Queue Status ==="
python -c "
import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
queues = ['backfin:queue:new_announcements', 'backfin:queue:ai_processing', 'backfin:queue:supabase_upload', 'backfin:queue:investor_processing']
for q in queues:
    length = r.llen(q)
    print(f'{q.split(\":\")[-1].upper()}: {length} jobs')
"
EOF

chmod +x /opt/backfin/monitor.sh
```

---

## 🔧 **Step 10: Start Your Backend Integration**

### **10.1 Test Integration**
```bash
cd /opt/backfin
source .venv/bin/activate

# Add a test job to see workers activate
python -c "
import redis
import json
import uuid
from datetime import datetime

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

job = {
    'job_id': str(uuid.uuid4()),
    'job_type': 'ai_processing',
    'corp_id': 'TEST_VM_001',
    'company_name': 'VM Test Company',
    'security_id': 'VMTEST',
    'created_at': datetime.now().isoformat(),
    'priority': 'normal',
    'retry_count': 0,
    'max_retries': 3,
    'timeout': 300,
    'metadata': {}
}

r.lpush('backfin:queue:ai_processing', json.dumps(job))
print('✅ Test job added - workers should spawn automatically!')
"
```

### **10.2 Watch Workers Activate**
```bash
# Monitor logs
tail -f /var/log/syslog | grep backfin

# Or check with monitoring script
./monitor.sh
```

---

## 🎯 **Step 11: Production Checklist**

### **11.1 Security Setup**
```bash
# Setup firewall (if needed)
sudo ufw allow 6379/tcp  # Redis
sudo ufw allow 8000/tcp  # Your backend

# Setup Redis password (recommended)
docker exec -it backfin-redis redis-cli CONFIG SET requirepass "your-secure-password"
```

### **11.2 Backup Strategy**
```bash
# Create backup script
cat > /opt/backfin/backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker exec backfin-redis redis-cli BGSAVE
docker cp backfin-redis:/data/dump.rdb /opt/backfin/backups/redis_$DATE.rdb
EOF

mkdir -p /opt/backfin/backups
chmod +x /opt/backfin/backup.sh
```

### **11.3 Log Rotation**
```bash
# Configure log rotation
sudo tee /etc/logrotate.d/backfin << 'EOF'
/opt/backfin/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
EOF
```

---

## 🔍 **Step 12: Verify Complete Deployment**

### **12.1 Final System Check**
```bash
cd /opt/backfin

# Check all components
echo "=== FINAL DEPLOYMENT VERIFICATION ==="

echo "✅ Redis:" && docker ps | grep redis
echo "✅ Worker Spawner:" && ps aux | grep worker_spawner | grep -v grep
echo "✅ Python Environment:" && source .venv/bin/activate && python --version
echo "✅ Queue System:" && python scripts/test_queue_system.py
echo "✅ File Permissions:" && ls -la workers/ephemeral_*.py

./monitor.sh
```

### **12.2 Performance Test**
```bash
# Run comprehensive test
python scripts/final_integration_test.py

# Run demo to see everything working
python scripts/demo_ephemeral_architecture.py
```

---

## 🎉 **Deployment Complete!**

Your Redis Queue Architecture is now running on your VM! Here's what you have:

### **✅ Active Services:**
- **Redis**: Running on port 6379
- **Worker Spawner**: Monitoring queues and spawning workers
- **Your Backend**: Still running on port 8000
- **Queue System**: Processing jobs automatically

### **✅ Integration Points:**
- Your backend can add jobs to Redis queues
- Workers automatically spawn and process jobs
- System scales up/down based on workload
- Complete monitoring and logging

### **🔧 Daily Operations:**
```bash
# Check system status
/opt/backfin/monitor.sh

# View live monitoring
cd /opt/backfin && source .venv/bin/activate && python scripts/live_monitor.py

# Add test job
python -c "import redis, json, uuid; r=redis.Redis(decode_responses=True); r.lpush('backfin:queue:ai_processing', json.dumps({'job_id': str(uuid.uuid4()), 'job_type': 'ai_processing', 'corp_id': 'TEST'}))"
```

**Your system is now production-ready on the VM! 🚀**