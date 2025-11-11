#!/usr/bin/env python3
"""
Backfin API Server - Main FastAPI application
Provides REST endpoints to interact with the Redis queue system
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import uuid

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import redis
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Backfin API",
    description="Redis Queue Management API for Stock Market Analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection
def get_redis_client():
    """Get Redis client connection"""
    try:
        client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0)),
            password=os.getenv('REDIS_PASSWORD'),
            decode_responses=True
        )
        client.ping()  # Test connection
        return client
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise HTTPException(status_code=503, detail="Redis connection failed")

# Pydantic models for API requests/responses
class AnnouncementRequest(BaseModel):
    """Model for new announcement processing requests"""
    company_name: str = Field(..., description="Company name")
    announcement_text: str = Field(..., description="Announcement content")
    announcement_date: Optional[str] = Field(None, description="Announcement date (ISO format)")
    source: str = Field(default="api", description="Source of announcement")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

class AIProcessingRequest(BaseModel):
    """Model for AI processing requests"""
    content: str = Field(..., description="Content to analyze")
    analysis_type: str = Field(default="general", description="Type of analysis")
    priority: int = Field(default=5, ge=1, le=10, description="Priority (1-10)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

class InvestorAnalysisRequest(BaseModel):
    """Model for investor analysis requests"""
    company_symbol: str = Field(..., description="Company stock symbol")
    analysis_period: str = Field(default="quarterly", description="Analysis period")
    data_sources: List[str] = Field(default=["financials", "announcements"], description="Data sources to analyze")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

class SupabaseUploadRequest(BaseModel):
    """Model for Supabase upload requests"""
    table_name: str = Field(..., description="Target table name")
    data: Dict[str, Any] = Field(..., description="Data to upload")
    operation: str = Field(default="insert", description="Database operation")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

class JobResponse(BaseModel):
    """Model for job submission responses"""
    job_id: str
    queue: str
    status: str
    message: str
    timestamp: str

class QueueStatusResponse(BaseModel):
    """Model for queue status responses"""
    queue_name: str
    job_count: int
    status: str

# API Endpoints

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Backfin API",
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    redis_client = get_redis_client()
    
    try:
        # Test Redis connection
        redis_info = redis_client.info()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
        redis_info = {}
    
    return {
        "status": "healthy" if redis_status == "healthy" else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "redis": {
                "status": redis_status,
                "memory_usage_mb": redis_info.get('used_memory', 0) / (1024 * 1024) if redis_info else 0,
                "connected_clients": redis_info.get('connected_clients', 0) if redis_info else 0
            }
        }
    }

@app.post("/jobs/announcement", response_model=JobResponse)
async def submit_announcement(request: AnnouncementRequest):
    """Submit a new announcement for processing"""
    redis_client = get_redis_client()
    
    job_id = str(uuid.uuid4())
    job_data = {
        "id": job_id,
        "company_name": request.company_name,
        "announcement_text": request.announcement_text,
        "announcement_date": request.announcement_date or datetime.now(timezone.utc).isoformat(),
        "source": request.source,
        "metadata": request.metadata,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        queue_name = "backfin:queue:new_announcements"
        redis_client.lpush(queue_name, json.dumps(job_data))
        
        logger.info(f"Submitted announcement job {job_id} for {request.company_name}")
        
        return JobResponse(
            job_id=job_id,
            queue=queue_name,
            status="submitted",
            message=f"Announcement job submitted for {request.company_name}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        logger.error(f"Failed to submit announcement job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit job: {str(e)}")

@app.post("/jobs/ai-analysis", response_model=JobResponse)
async def submit_ai_analysis(request: AIProcessingRequest):
    """Submit content for AI analysis"""
    redis_client = get_redis_client()
    
    job_id = str(uuid.uuid4())
    job_data = {
        "id": job_id,
        "content": request.content,
        "analysis_type": request.analysis_type,
        "priority": request.priority,
        "metadata": request.metadata,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        queue_name = "backfin:queue:ai_processing"
        redis_client.lpush(queue_name, json.dumps(job_data))
        
        logger.info(f"Submitted AI analysis job {job_id}")
        
        return JobResponse(
            job_id=job_id,
            queue=queue_name,
            status="submitted",
            message=f"AI analysis job submitted with priority {request.priority}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        logger.error(f"Failed to submit AI analysis job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit job: {str(e)}")

@app.post("/jobs/investor-analysis", response_model=JobResponse)
async def submit_investor_analysis(request: InvestorAnalysisRequest):
    """Submit company data for investor analysis"""
    redis_client = get_redis_client()
    
    job_id = str(uuid.uuid4())
    job_data = {
        "id": job_id,
        "company_symbol": request.company_symbol,
        "analysis_period": request.analysis_period,
        "data_sources": request.data_sources,
        "metadata": request.metadata,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        queue_name = "backfin:queue:investor_processing"
        redis_client.lpush(queue_name, json.dumps(job_data))
        
        logger.info(f"Submitted investor analysis job {job_id} for {request.company_symbol}")
        
        return JobResponse(
            job_id=job_id,
            queue=queue_name,
            status="submitted",
            message=f"Investor analysis job submitted for {request.company_symbol}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        logger.error(f"Failed to submit investor analysis job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit job: {str(e)}")

@app.post("/jobs/supabase-upload", response_model=JobResponse)
async def submit_supabase_upload(request: SupabaseUploadRequest):
    """Submit data for Supabase upload"""
    redis_client = get_redis_client()
    
    job_id = str(uuid.uuid4())
    job_data = {
        "id": job_id,
        "table_name": request.table_name,
        "data": request.data,
        "operation": request.operation,
        "metadata": request.metadata,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        queue_name = "backfin:queue:supabase_upload"
        redis_client.lpush(queue_name, json.dumps(job_data))
        
        logger.info(f"Submitted Supabase upload job {job_id} for table {request.table_name}")
        
        return JobResponse(
            job_id=job_id,
            queue=queue_name,
            status="submitted",
            message=f"Supabase upload job submitted for table {request.table_name}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        logger.error(f"Failed to submit Supabase upload job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit job: {str(e)}")

@app.get("/queues/status", response_model=List[QueueStatusResponse])
async def get_queue_status():
    """Get status of all queues"""
    redis_client = get_redis_client()
    
    queues = [
        "backfin:queue:new_announcements",
        "backfin:queue:ai_processing", 
        "backfin:queue:supabase_upload",
        "backfin:queue:investor_processing",
        "backfin:queue:scraper_jobs",
        "backfin:queue:email_notifications",
        "backfin:queue:priority_jobs"
    ]
    
    status_list = []
    
    for queue in queues:
        try:
            job_count = redis_client.llen(queue)
            status = "active" if job_count > 0 else "idle"
            
            status_list.append(QueueStatusResponse(
                queue_name=queue.split(":")[-1],
                job_count=job_count,
                status=status
            ))
        except Exception as e:
            logger.error(f"Failed to get status for queue {queue}: {e}")
            status_list.append(QueueStatusResponse(
                queue_name=queue.split(":")[-1],
                job_count=0,
                status="error"
            ))
    
    return status_list

@app.get("/queues/{queue_name}/jobs")
async def get_queue_jobs(queue_name: str, limit: int = 10):
    """Get jobs from a specific queue (without removing them)"""
    redis_client = get_redis_client()
    
    full_queue_name = f"backfin:queue:{queue_name}"
    
    try:
        # Get jobs from the queue (peek without removing)
        jobs_raw = redis_client.lrange(full_queue_name, 0, limit - 1)
        jobs = []
        
        for job_raw in jobs_raw:
            try:
                job_data = json.loads(job_raw)
                jobs.append(job_data)
            except json.JSONDecodeError:
                jobs.append({"raw": job_raw, "error": "Invalid JSON"})
        
        return {
            "queue_name": queue_name,
            "total_jobs": redis_client.llen(full_queue_name),
            "jobs": jobs
        }
    except Exception as e:
        logger.error(f"Failed to get jobs from queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get queue jobs: {str(e)}")

@app.delete("/queues/{queue_name}")
async def clear_queue(queue_name: str):
    """Clear all jobs from a specific queue"""
    redis_client = get_redis_client()
    
    full_queue_name = f"backfin:queue:{queue_name}"
    
    try:
        cleared_count = redis_client.delete(full_queue_name)
        
        logger.info(f"Cleared queue {queue_name}")
        
        return {
            "queue_name": queue_name,
            "message": f"Queue {queue_name} cleared",
            "jobs_cleared": cleared_count > 0
        }
    except Exception as e:
        logger.error(f"Failed to clear queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear queue: {str(e)}")

@app.get("/stats")
async def get_system_stats():
    """Get comprehensive system statistics"""
    redis_client = get_redis_client()
    
    try:
        # Redis info
        redis_info = redis_client.info()
        
        # Queue statistics
        queues = [
            "backfin:queue:new_announcements",
            "backfin:queue:ai_processing",
            "backfin:queue:supabase_upload", 
            "backfin:queue:investor_processing",
            "backfin:queue:scraper_jobs",
            "backfin:queue:email_notifications",
            "backfin:queue:priority_jobs"
        ]
        
        queue_stats = {}
        total_jobs = 0
        
        for queue in queues:
            job_count = redis_client.llen(queue)
            queue_stats[queue.split(":")[-1]] = job_count
            total_jobs += job_count
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "redis": {
                "memory_usage_mb": redis_info.get('used_memory', 0) / (1024 * 1024),
                "connected_clients": redis_info.get('connected_clients', 0),
                "total_commands_processed": redis_info.get('total_commands_processed', 0),
                "uptime_seconds": redis_info.get('uptime_in_seconds', 0)
            },
            "queues": queue_stats,
            "total_pending_jobs": total_jobs
        }
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Endpoint not found", "message": "The requested endpoint does not exist"}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": "An unexpected error occurred"}
    )

if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8000))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    logger.info(f"Starting Backfin API server on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )