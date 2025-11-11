#!/usr/bin/env python3
"""
Quick Start Server - Single command to run the entire Backfin system
This script starts the API server and worker spawner together
"""

import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path

def run_command(cmd, name, cwd=None):
    """Run a command in a separate process"""
    print(f"🚀 Starting {name}...")
    try:
        process = subprocess.Popen(
            cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Print output in real-time
        for line in iter(process.stdout.readline, ''):
            if line.strip():
                print(f"[{name}] {line.strip()}")
        
        return process
    except Exception as e:
        print(f"❌ Failed to start {name}: {e}")
        return None

def check_redis():
    """Check if Redis is running"""
    try:
        import redis
        client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        client.ping()
        print("✅ Redis is running")
        return True
    except Exception as e:
        print(f"❌ Redis not available: {e}")
        return False

def start_redis():
    """Start Redis using Docker"""
    print("🔄 Starting Redis with Docker...")
    
    # Check if Redis container already exists
    check_cmd = "docker ps -a --filter name=backfin-redis --format '{{.Names}}'"
    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
    
    if "backfin-redis" in result.stdout:
        # Container exists, start it
        subprocess.run("docker start backfin-redis", shell=True)
    else:
        # Create new container
        subprocess.run(
            "docker run -d --name backfin-redis -p 6379:6379 redis:7-alpine",
            shell=True
        )
    
    # Wait for Redis to be ready
    for i in range(10):
        if check_redis():
            return True
        time.sleep(1)
    
    return False

def main():
    """Main function to start the entire system"""
    print("🎯 BACKFIN SYSTEM STARTUP")
    print("=" * 50)
    
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Check if we're in a virtual environment
    if not os.environ.get('VIRTUAL_ENV'):
        print("⚠️  Warning: Not in a virtual environment")
        print("   Recommended: source .venv/bin/activate")
    
    # Step 1: Check/Start Redis
    if not check_redis():
        if not start_redis():
            print("❌ Failed to start Redis. Please start it manually:")
            print("   docker run -d --name backfin-redis -p 6379:6379 redis:7-alpine")
            sys.exit(1)
    
    # Step 2: Set environment variables
    os.environ.setdefault('REDIS_HOST', 'localhost')
    os.environ.setdefault('REDIS_PORT', '6379')
    os.environ.setdefault('API_HOST', '0.0.0.0')
    os.environ.setdefault('API_PORT', '8000')
    
    print("✅ Environment configured")
    
    # Step 3: Start services
    processes = []
    
    try:
        # Start Worker Spawner
        spawner_process = run_command(
            "python management/worker_spawner.py",
            "Worker Spawner",
            cwd=project_root
        )
        if spawner_process:
            processes.append(("Worker Spawner", spawner_process))
        
        # Wait a bit for spawner to initialize
        time.sleep(2)
        
        # Start API Server
        api_process = run_command(
            "python api/main.py",
            "API Server",
            cwd=project_root
        )
        if api_process:
            processes.append(("API Server", api_process))
        
        print("\n🎉 SYSTEM STARTED SUCCESSFULLY!")
        print("=" * 50)
        print("📊 API Documentation: http://localhost:8000/docs")
        print("🔍 Health Check: http://localhost:8000/health")
        print("📈 Queue Status: http://localhost:8000/queues/status")
        print("📊 System Stats: http://localhost:8000/stats")
        print("\n💡 Example API calls:")
        print("curl -X POST http://localhost:8000/jobs/announcement \\")
        print("  -H 'Content-Type: application/json' \\")
        print("  -d '{\"company_name\": \"RELIANCE\", \"announcement_text\": \"Q3 earnings released\"}'")
        print("\n⏹️  Press Ctrl+C to stop all services")
        
        # Wait for interrupt
        try:
            while True:
                # Check if processes are still running
                for name, process in processes:
                    if process.poll() is not None:
                        print(f"⚠️  {name} stopped unexpectedly")
                
                time.sleep(5)
        
        except KeyboardInterrupt:
            print("\n🛑 Stopping services...")
            
            # Gracefully stop all processes
            for name, process in processes:
                print(f"   Stopping {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            
            print("✅ All services stopped")
    
    except Exception as e:
        print(f"❌ Error during startup: {e}")
        
        # Clean up processes
        for name, process in processes:
            if process and process.poll() is None:
                process.terminate()
        
        sys.exit(1)

if __name__ == "__main__":
    main()