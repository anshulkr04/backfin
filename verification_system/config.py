# Verification System Configuration
import os
from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import Field

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # API Configuration
    APP_NAME: str = "Backfin Verification System"
    APP_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/admin"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 5002
    
    # Environment
    PROD: bool = False
    
    # Supabase Configuration - Using SUPABASE_URL2 and SUPABASE_KEY2
    SUPABASE_URL2: str = Field(alias="SUPABASE_URL2")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(alias="SUPABASE_SERVICE_ROLE_KEY")
    
    # JWT Configuration
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    
    # Gemini AI Configuration
    GEMINI_API_KEY: str = ""
    
    # Session Configuration
    SESSION_TIMEOUT_MINUTES: int = 30
    
    # Task Management
    TASK_TIMEOUT_MINUTES: int = 30  # Release tasks if not completed
    
    # CORS Configuration
    CORS_ORIGINS: str = "*"  # Comma-separated string or "*" for all origins
    
    class Config:
        # Load from main .env file in parent directory
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from main .env file

# Global settings instance
settings = Settings()
