"""
FastAPI Application Entry Point.

This is where everything comes together. FastAPI creates a web server
that listens for HTTP requests and routes them to the right handler.

HOW THE REQUEST FLOW WORKS:

    Browser/curl/frontend
        ↓ HTTP POST /api/analyze {"diff_text": "..."}
    FastAPI (this file)
        ↓ validates request body against PRInput schema
    Routes (routes.py)
        ↓ calls analysis_service.analyze_diff()
    Analysis Service (analysis_service.py)
        ↓ runs SecurityAgent.analyze()
    SecurityAgent (security_agent.py)
        ↓ builds prompt, calls Ollama
    OllamaClient (ollama_client.py)
        ↓ HTTP POST to localhost:11434/api/generate
    Ollama (local LLM)
        ↓ returns JSON response
    Back up the chain → HTTP 200 with AnalysisResult JSON

TO RUN:
    cd pr-review-ai
    venv/Scripts/python -m uvicorn backend.api.main:app --reload

    Then visit: http://localhost:8000/docs (Swagger UI)
"""

import uuid

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.api.websocket import manager, handle_analysis
from backend.config import settings


app = FastAPI(
    title="PR Review AI",
    description="Agentic AI system that analyzes Pull Requests for security "
                "vulnerabilities, performance issues, and more.",
    version="0.1.0",
)

# CORS Middleware
# WHY? The frontend (React on localhost:5173) needs to call the backend
# (FastAPI on localhost:8000). Browsers block this by default ("same-origin policy").
# CORS headers tell the browser "it's OK, I trust this origin."
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server (React frontend)
        "http://localhost:3000",   # Alternative frontend port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router)


@app.get("/")
async def root():
    """
    Root endpoint - simple welcome message.

    Also serves as a quick health check:
    if this responds, the server is running.
    """
    return {
        "name": "PR Review AI",
        "version": "0.1.0",
        "docs": "/docs",
        "status": "running",
    }


@app.websocket("/ws/analyze")
async def websocket_analyze(websocket: WebSocket):
    """
    WebSocket endpoint for real-time analysis streaming.

    Flow:
        1. Client connects -> gets a unique session_id
        2. Client sends {"diff_text": "..."} or {"pr_url": "..."}
        3. Server streams events as each agent starts/completes
        4. Final event contains the full AnalysisResult
        5. Connection closes

    Events sent to client:
        - fetch_started / fetch_completed  (if PR URL)
        - analysis_started
        - agent_started (x5)
        - agent_completed (x5, as each finishes)
        - analysis_completed (final result)
        - error (if something goes wrong)
    """
    session_id = str(uuid.uuid4())[:8]
    await manager.connect(websocket, session_id)

    try:
        await handle_analysis(websocket, session_id)
    finally:
        manager.disconnect(session_id)
