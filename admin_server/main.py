import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
import uvicorn

# Load environment variables from parent directory
load_dotenv('/Users/anshulkumar/backfin/.env')

from routes.auth import router as auth_router
from routes.tasks import router as tasks_router
from routes.admin import router as admin_router
from services.task_manager import TaskManager
from services.reclaim_service import ReclaimService
from services.websocket_manager import WebSocketManager
from services.queue_processor import QueueProcessor

# Global instances
task_manager = None
reclaim_service = None
websocket_manager = None
queue_processor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global task_manager, reclaim_service, websocket_manager, queue_processor
    
    print("🚀 Starting Admin Server...")
    
    # Initialize task manager
    task_manager = TaskManager()
    await task_manager.initialize()
    
    # Initialize WebSocket manager (needs task_manager)
    websocket_manager = WebSocketManager(task_manager)
    
    # Initialize reclaim service
    reclaim_service = ReclaimService(task_manager)
    await reclaim_service.start()
    
    # Initialize queue processor (listens to main Flask app)
    queue_processor = QueueProcessor(task_manager)
    await queue_processor.start()
    
    # Inject dependencies into route modules
    from routes.tasks import router as tasks_router
    from routes.admin import router as admin_router
    
    tasks_router.task_manager = task_manager
    tasks_router.websocket_manager = websocket_manager
    
    admin_router.task_manager = task_manager
    admin_router.reclaim_service = reclaim_service
    admin_router.websocket_manager = websocket_manager
    
    print("✅ All services started successfully!")
    yield
    
    # Cleanup
    print("🛑 Shutting down Admin Server...")
    
    if queue_processor:
        await queue_processor.stop()
    
    if reclaim_service:
        await reclaim_service.stop()
    
    if task_manager:
        await task_manager.cleanup()
    
    print("✅ Cleanup completed!")

# Create FastAPI app
app = FastAPI(
    title="Backfin Admin Verification System",
    description="Admin interface for verifying AI-processed announcements",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:9000"],  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(tasks_router, prefix="/tasks", tags=["Tasks"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle client messages
            data = await websocket.receive_text()
            # Handle any client messages if needed
            print(f"Received WebSocket message: {data}")
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)

# Root endpoint - serve admin interface
@app.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        with open("static/index.html", "r") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Admin Interface</h1><p>Frontend not found. Please check static/index.html</p>",
            status_code=404
        )

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "admin-verification-server",
        "port": 9000,
        "task_manager": task_manager is not None,
        "reclaim_service": reclaim_service is not None,
        "websocket_manager": websocket_manager is not None
    }

if __name__ == "__main__":
    port = int(os.getenv("ADMIN_PORT", 9000))
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port, 
        reload=True,
        log_level="info"
    )