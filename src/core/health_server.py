"""
Health check server for Backfin services
Provides HTTP endpoints for Kubernetes health checks
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import redis
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Backfin Health Check", version="1.0.0")

# Service configuration
SERVICE_NAME = os.getenv('SERVICE_NAME', 'unknown')
WORKER_TYPE = os.getenv('WORKER_TYPE', 'unknown')
PORT = int(os.getenv('PORT', 8080))

# Redis connection for health checks
def get_redis_connection():
    """Get Redis connection for health checks"""
    try:
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        redis_db = int(os.getenv('REDIS_DB', 0))
        
        r = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True
        )
        r.ping()  # Test connection
        return r
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return None

@app.get("/health")
async def health_check():
    """Kubernetes liveness probe endpoint"""
    try:
        # Basic health check
        status = {
            "status": "healthy",
            "service": SERVICE_NAME,
            "worker_type": WORKER_TYPE,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": "unknown"
        }
        
        # Check Redis connectivity
        redis_conn = get_redis_connection()
        if redis_conn:
            status["redis"] = "connected"
        else:
            status["redis"] = "disconnected"
            status["status"] = "degraded"
        
        return JSONResponse(content=status, status_code=200)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            },
            status_code=503
        )

@app.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe endpoint"""
    try:
        # More thorough readiness check
        redis_conn = get_redis_connection()
        if not redis_conn:
            raise HTTPException(
                status_code=503,
                detail="Redis connection not available"
            )
        
        # Service-specific readiness checks
        status = {
            "status": "ready",
            "service": SERVICE_NAME,
            "worker_type": WORKER_TYPE,
            "timestamp": datetime.utcnow().isoformat(),
            "redis": "connected"
        }
        
        return JSONResponse(content=status, status_code=200)
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            content={
                "status": "not_ready",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            },
            status_code=503
        )

@app.get("/metrics")
async def metrics():
    """Basic metrics endpoint for monitoring"""
    try:
        redis_conn = get_redis_connection()
        metrics = {
            "service": SERVICE_NAME,
            "worker_type": WORKER_TYPE,
            "timestamp": datetime.utcnow().isoformat(),
            "redis_connected": redis_conn is not None
        }
        
        if redis_conn:
            # Get basic Redis stats
            info = redis_conn.info()
            metrics.update({
                "redis_used_memory": info.get('used_memory', 0),
                "redis_connected_clients": info.get('connected_clients', 0),
                "redis_total_commands_processed": info.get('total_commands_processed', 0)
            })
        
        return JSONResponse(content=metrics, status_code=200)
    except Exception as e:
        logger.error(f"Metrics failed: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=503
        )

def run_health_server():
    """Run the health check server"""
    logger.info(f"Starting health server for {SERVICE_NAME} on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

if __name__ == "__main__":
    run_health_server()