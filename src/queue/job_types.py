"""
Job type definitions for the Redis Queue system
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum

class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"

class JobPriority(str, Enum):
    """Job priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class BaseJob(BaseModel):
    """Base job model with common fields"""
    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Type of job")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    priority: JobPriority = Field(default=JobPriority.NORMAL)
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    timeout: int = Field(default=300)  # 5 minutes default
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AnnouncementScrapingJob(BaseJob):
    """Job for scraping new announcements from BSE/NSE"""
    job_type: str = "announcement_scraping"
    source: str = Field(..., description="Source exchange (BSE/NSE)")
    last_processed_time: Optional[datetime] = None
    
class AIProcessingJob(BaseJob):
    """Job for AI processing of announcements"""
    job_type: str = "ai_processing"
    corp_id: str = Field(..., description="Corporate filing ID")
    announcement_data: Dict[str, Any] = Field(..., description="Raw announcement data from BSE/NSE")
    pdf_url: Optional[str] = None
    summary_text: Optional[str] = None
    company_name: str = ""
    security_id: str = ""
    
class SupabaseUploadJob(BaseJob):
    """Job for uploading processed data to Supabase"""
    job_type: str = "supabase_upload"
    corp_id: str = Field(..., description="Corporate filing ID")
    processed_data: Dict[str, Any] = Field(..., description="AI processed data")
    update_existing: bool = Field(default=False)
    
class InvestorAnalysisJob(BaseJob):
    """Job for investor analysis and notifications"""
    job_type: str = "investor_analysis"
    corp_id: str = Field(..., description="Corporate filing ID")
    category: str = ""
    individual_investors: List[str] = Field(default_factory=list)
    company_investors: List[str] = Field(default_factory=list)
    
class FailedJob(BaseJob):
    """Job that failed and needs retry or investigation"""
    job_type: str = "failed_job"
    original_job_type: str = Field(..., description="Original job type that failed")
    original_job_data: Dict[str, Any] = Field(..., description="Original job payload")
    error_message: str = ""
    error_traceback: str = ""
    failed_at: datetime = Field(default_factory=datetime.utcnow)

# Job type mapping for deserialization
JOB_TYPE_MAPPING = {
    "announcement_scraping": AnnouncementScrapingJob,
    "ai_processing": AIProcessingJob,
    "supabase_upload": SupabaseUploadJob,
    "investor_analysis": InvestorAnalysisJob,
    "failed_job": FailedJob,
}

def create_job_from_dict(job_data: Dict[str, Any]) -> BaseJob:
    """Create appropriate job object from dictionary"""
    job_type = job_data.get('job_type')
    job_class = JOB_TYPE_MAPPING.get(job_type, BaseJob)
    return job_class(**job_data)

def serialize_job(job: BaseJob) -> str:
    """Serialize job to JSON string for Redis"""
    return job.model_dump_json()

def deserialize_job(job_json: str) -> BaseJob:
    """Deserialize job from JSON string"""
    import json
    job_data = json.loads(job_json)
    return create_job_from_dict(job_data)