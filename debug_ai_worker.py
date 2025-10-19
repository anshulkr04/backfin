#!/usr/bin/env python3
"""
Debug script to test AI worker imports and basic functionality
"""
import sys
import logging
from pathlib import Path

# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("debug_ai_worker")

logger.info("🔍 Starting AI worker debug test...")

# Test path setup
sys.path.append(str(Path(__file__).parent))
logger.info(f"✅ Python path setup complete")

# Test basic imports
try:
    import redis
    logger.info("✅ Redis import successful")
except ImportError as e:
    logger.error(f"❌ Redis import failed: {e}")

try:
    from pydantic import BaseModel, Field
    logger.info("✅ Pydantic import successful")
except ImportError as e:
    logger.error(f"❌ Pydantic import failed: {e}")

# Test Google AI imports
try:
    from google import genai
    logger.info("✅ Google GenAI import successful")
except ImportError as e:
    logger.error(f"❌ Google GenAI import failed: {e}")

try:
    from google.genai import types
    logger.info("✅ Google GenAI types import successful")
except ImportError as e:
    logger.error(f"❌ Google GenAI types import failed: {e}")

# Test queue imports
try:
    from src.queue.redis_client import RedisConfig, QueueNames
    logger.info("✅ Queue client imports successful")
except ImportError as e:
    logger.error(f"❌ Queue client imports failed: {e}")

try:
    from src.queue.job_types import deserialize_job, AIProcessingJob, SupabaseUploadJob, serialize_job
    logger.info("✅ Job types imports successful")
except ImportError as e:
    logger.error(f"❌ Job types imports failed: {e}")

# Test AI prompts import
try:
    from src.ai.prompts import *
    logger.info("✅ AI prompts import successful")
except ImportError as e:
    logger.error(f"❌ AI prompts import failed: {e}")

# Test Redis connection
try:
    from src.queue.redis_client import get_redis_client
    redis_client = get_redis_client()
    redis_client.ping()
    logger.info("✅ Redis connection successful")
except Exception as e:
    logger.error(f"❌ Redis connection failed: {e}")

logger.info("🎯 Debug test completed!")