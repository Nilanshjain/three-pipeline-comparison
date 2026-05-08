# Our main FastAPI application
# This file is the entry point - where everything starts

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import upload, chat, metrics, benchmark  # Import our routers

# Create our FastAPI application instance
# Think of this as creating our restaurant
app = FastAPI(
    title="DevRAG API",  # Name of our API
    description="A RAG system for chatting with your documents and code",
    version="1.0.0"  # Version number for tracking changes
)

# Add CORS middleware - allows frontend to talk to backend
# CORS = Cross-Origin Resource Sharing
# Without this, browsers block requests from localhost:3000 to localhost:8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React app URL
    allow_credentials=True,  # Allow cookies and auth headers
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Our first API endpoint - like a specific item on the menu
@app.get("/")  # HTTP GET request to the root URL "/"
async def read_root():
    """
    Root endpoint - shows our API is working

    This is like the front door of our restaurant.
    When someone visits http://localhost:8000/, they get this response.
    """
    return {
        "message": "Welcome to DevRAG API! 🤖",
        "status": "running",
        "docs_url": "/docs"  # Tell users where to find API documentation
    }

# Health check endpoint - used to verify our service is working
@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring

    This is like asking "Is the kitchen working?"
    Useful for deployment systems and monitoring tools.
    """
    return {"status": "healthy", "service": "devrag-api"}

# API endpoint to get basic information about our service
@app.get("/info")
async def get_info():
    """
    Returns information about our API capabilities

    This tells users what our API can do.
    """
    return {
        "name": "DevRAG",
        "version": "1.0.0",
        "description": "Chat with your documents and code using AI",
        "features": [
            "Document upload and processing",
            "AI-powered question answering",
            "Code-aware responses",
            "Real-time chat interface"
        ],
        "endpoints": {
            "docs": "/docs",  # Automatic API documentation
            "health": "/health",
            "upload": "/upload (coming soon)",
            "chat": "/chat (coming soon)"
        }
    }

# Include routers
# This adds all the endpoints from our API modules to the main app
app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(metrics.router)
app.include_router(benchmark.router)