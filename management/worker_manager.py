"""
Worker management utilities for starting, stopping, and monitoring workers
"""

import subprocess
import psutil
import time
import signal
import os
from typing import List, Dict, Any
from datetime import datetime

class WorkerManager:
    """Manager for worker processes"""
    
    def __init__(self):
        self.worker_processes = {}
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    def start_worker(self, worker_type: str, worker_id: str = None) -> bool:
        """Start a worker process"""
        worker_scripts = {
            "scraper": "workers/start_scraper_worker.py",
            "ai": "workers/start_ai_worker.py", 
            "database": "workers/start_db_worker.py",
            "investor": "workers/start_investor_worker.py",
            "replay": "workers/replay_processor.py"
        }
        
        script_path = worker_scripts.get(worker_type)
        if not script_path:
            print(f"Unknown worker type: {worker_type}")
            return False
        
        full_script_path = os.path.join(self.base_dir, script_path)
        if not os.path.exists(full_script_path):
            print(f"Worker script not found: {full_script_path}")
            return False
        
        worker_id = worker_id or f"{worker_type}_{int(time.time())}"
        
        try:
            process = subprocess.Popen(
                ["python", full_script_path],
                cwd=self.base_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.worker_processes[worker_id] = {
                "type": worker_type,
                "process": process,
                "started_at": datetime.now(),
                "pid": process.pid
            }
            
            print(f"Started {worker_type} worker (ID: {worker_id}, PID: {process.pid})")
            return True
            
        except Exception as e:
            print(f"Failed to start {worker_type} worker: {e}")
            return False
    
    def stop_worker(self, worker_id: str) -> bool:
        """Stop a specific worker"""
        if worker_id not in self.worker_processes:
            print(f"Worker {worker_id} not found")
            return False
        
        worker_info = self.worker_processes[worker_id]
        process = worker_info["process"]
        
        try:
            # Try graceful shutdown first
            process.terminate()
            process.wait(timeout=10)
            
        except subprocess.TimeoutExpired:
            # Force kill if graceful shutdown fails
            process.kill()
            process.wait()
        
        except Exception as e:
            print(f"Error stopping worker {worker_id}: {e}")
            return False
        
        del self.worker_processes[worker_id]
        print(f"Stopped worker {worker_id}")
        return True
    
    def stop_all_workers(self):
        """Stop all managed workers"""
        worker_ids = list(self.worker_processes.keys())
        for worker_id in worker_ids:
            self.stop_worker(worker_id)
    
    def get_worker_status(self) -> List[Dict[str, Any]]:
        """Get status of all workers"""
        status_list = []
        
        for worker_id, worker_info in self.worker_processes.items():
            process = worker_info["process"]
            
            # Check if process is still running
            try:
                psutil_process = psutil.Process(process.pid)
                is_running = psutil_process.is_running()
                cpu_percent = psutil_process.cpu_percent()
                memory_mb = psutil_process.memory_info().rss / 1024 / 1024
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                is_running = False
                cpu_percent = 0
                memory_mb = 0
            
            status_list.append({
                "worker_id": worker_id,
                "type": worker_info["type"],
                "pid": worker_info["pid"],
                "running": is_running,
                "started_at": worker_info["started_at"].strftime("%Y-%m-%d %H:%M:%S"),
                "cpu_percent": cpu_percent,
                "memory_mb": round(memory_mb, 1)
            })
        
        return status_list
    
    def print_status(self):
        """Print formatted worker status"""
        print("=" * 80)
        print(f"Worker Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        status_list = self.get_worker_status()
        
        if not status_list:
            print("No managed workers running")
            return
        
        print(f"{'ID':<15} {'Type':<10} {'PID':<8} {'Status':<8} {'CPU%':<6} {'RAM(MB)':<8} {'Started'}")
        print("-" * 80)
        
        for worker in status_list:
            status = "Running" if worker["running"] else "Stopped"
            print(f"{worker['worker_id']:<15} {worker['type']:<10} {worker['pid']:<8} "
                  f"{status:<8} {worker['cpu_percent']:<6.1f} {worker['memory_mb']:<8} {worker['started_at']}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all workers"""
        status_list = self.get_worker_status()
        
        total_workers = len(status_list)
        running_workers = sum(1 for w in status_list if w["running"])
        
        health = {
            "total_workers": total_workers,
            "running_workers": running_workers,
            "stopped_workers": total_workers - running_workers,
            "healthy": running_workers == total_workers and total_workers > 0
        }
        
        return health

def main():
    """CLI interface for worker management"""
    import sys
    
    manager = WorkerManager()
    
    if len(sys.argv) < 2:
        print("Usage: python worker_manager.py [start|stop|status|health] [worker_type] [worker_id]")
        print("Worker types: scraper, ai, database, investor, replay")
        return
    
    command = sys.argv[1].lower()
    
    if command == "start" and len(sys.argv) > 2:
        worker_type = sys.argv[2]
        worker_id = sys.argv[3] if len(sys.argv) > 3 else None
        manager.start_worker(worker_type, worker_id)
    
    elif command == "stop":
        if len(sys.argv) > 2:
            worker_id = sys.argv[2]
            manager.stop_worker(worker_id)
        else:
            manager.stop_all_workers()
    
    elif command == "status":
        manager.print_status()
    
    elif command == "health":
        health = manager.health_check()
        print(f"Health Status: {'Healthy' if health['healthy'] else 'Unhealthy'}")
        print(f"Workers: {health['running_workers']}/{health['total_workers']} running")
    
    else:
        print("Invalid command or missing arguments")

if __name__ == "__main__":
    main()