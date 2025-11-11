import asyncio
import json
import logging
import uuid
from typing import Dict, Any
from datetime import datetime

from services.task_manager import TaskManager

# Try to import Supabase service, fall back to mock if not available
try:
    from services.supabase_client import supabase_service
except ImportError:
    from services.mock_supabase import supabase_service

logger = logging.getLogger(__name__)

class QueueProcessor:
    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager
        self.is_running = False
        self.stream_name = "admin:verification:stream"
        
    async def start(self):
        """Start processing the queue from main Flask app"""
        if self.is_running:
            return
            
        self.is_running = True
        logger.info("🎯 Starting queue processor...")
        
        # Start background task
        asyncio.create_task(self._process_queue())
        
    async def stop(self):
        """Stop processing the queue"""
        self.is_running = False
        logger.info("⏹️ Stopped queue processor")
        
    async def _process_queue(self):
        """Main queue processing loop"""
        while self.is_running:
            try:
                # Read new messages from the stream
                messages = await self.task_manager.redis_client.xread(
                    {self.stream_name: '$'},  # Read only new messages
                    block=5000,  # Block for 5 seconds
                    count=10
                )
                
                if messages:
                    for stream_name, stream_messages in messages:
                        for message_id, fields in stream_messages:
                            await self._process_message(message_id, fields)
                            
            except Exception as e:
                logger.error(f"❌ Error in queue processor: {e}")
                await asyncio.sleep(5)  # Wait before retrying
                
    async def _process_message(self, message_id: str, fields: Dict[str, str]):
        """Process a single message from the queue"""
        try:
            # Parse the message from main Flask app
            announcement_data = json.loads(fields.get('announcement', '{}'))
            original_data = json.loads(fields.get('original_data', '{}'))
            ai_summary = fields.get('ai_summary', '')
            created_at = fields.get('created_at')
            
            # Create task in verification database
            task_id = await self._create_verification_task(
                announcement_data=announcement_data,
                original_data=original_data,
                ai_summary=ai_summary,
                created_at=created_at
            )
            
            if task_id:
                logger.info(f"✅ Created verification task {task_id} from message {message_id}")
                
                # Add to our task queue for workers to claim
                await self.task_manager.add_task_to_stream(task_id, {
                    "announcement_data": announcement_data,
                    "original_data": original_data,
                    "ai_summary": ai_summary,
                    "source_message_id": message_id
                })
            else:
                logger.error(f"❌ Failed to create verification task from message {message_id}")
                
        except Exception as e:
            logger.error(f"❌ Error processing message {message_id}: {e}")
            
    async def _create_verification_task(
        self, 
        announcement_data: Dict[str, Any],
        original_data: Dict[str, Any], 
        ai_summary: str,
        created_at: str = None
    ) -> str:
        """Create a verification task in the database"""
        try:
            # For mock service, create the task directly
            task_id = str(uuid.uuid4())
            
            # Create verification task
            task_data = {
                "id": task_id,
                "announcement_id": f"announcement_{task_id}",  # Mock announcement ID
                "original_data": original_data,
                "current_data": original_data,  # Start with original data
                "ai_summary": ai_summary,
                "status": "pending",
                "has_edits": False,
                "edit_count": 0,
                "created_at": created_at or datetime.utcnow().isoformat(),
                "assigned_to_user": None,
                "assigned_at": None
            }
            
            # Store in mock database if using mock service
            if hasattr(supabase_service, 'tasks'):
                supabase_service.tasks[task_id] = task_data
                logger.info(f"✅ Created verification task {task_id} in mock database")
                return task_id
            else:
                # If using real Supabase, use the original method
                result = await supabase_service.client.table("verification_tasks").insert(task_data).execute()
                
                if result.data:
                    return str(result.data[0]["id"])
                else:
                    logger.error("Failed to insert verification task")
                    return None
                
        except Exception as e:
            logger.error(f"Error creating verification task: {e}")
            return None
            
    async def _ensure_announcement_exists(self, announcement_data: Dict[str, Any], original_data: Dict[str, Any]) -> str:
        """Ensure announcement exists in corporatefilings table"""
        try:
            # Try to find existing announcement by corp_id or other unique identifier
            corp_id = original_data.get('corp_id') or announcement_data.get('corp_id')
            
            if corp_id:
                # Check if announcement already exists
                result = await supabase_service.client.table("corporatefilings").select("id").eq(
                    "corp_id", corp_id
                ).execute()
                
                if result.data:
                    return str(result.data[0]["id"])
            
            # Create new announcement record
            filing_data = {
                "corp_id": corp_id,
                "title": announcement_data.get('title', ''),
                "category": announcement_data.get('category', ''),
                "fileurl": announcement_data.get('fileurl', ''),
                "date": announcement_data.get('date', ''),
                "ai_summary": announcement_data.get('ai_summary', ''),
                "isin": announcement_data.get('isin', ''),
                "companyname": announcement_data.get('companyname', ''),
                "symbol": announcement_data.get('symbol', ''),
                "created_at": datetime.utcnow().isoformat()
            }
            
            result = await supabase_service.client.table("corporatefilings").insert(filing_data).execute()
            
            if result.data:
                return str(result.data[0]["id"])
            else:
                logger.error("Failed to create announcement record")
                return None
                
        except Exception as e:
            logger.error(f"Error ensuring announcement exists: {e}")
            return None