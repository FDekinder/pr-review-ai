"""
API Routes - HTTP endpoints for the PR Review system.

FASTAPI KEY CONCEPTS:
1. Decorators (@router.post) map URLs to functions
2. Pydantic models validate request/response data automatically
3. async def = non-blocking (can handle many requests simultaneously)
4. HTTPException = proper error responses with status codes
5. Dependency Injection = FastAPI creates/manages shared resources

ENDPOINTS:
    POST /api/analyze         → Submit code for analysis
    GET  /api/analysis/{id}   → Get results by ID
    GET  /api/history         → List recent analyses
    GET  /api/health          → System health check
"""

from fastapi import APIRouter, HTTPException

from backend.models.schemas import AnalysisResult, PRInput
from backend.services.analysis_service import AnalysisService

# APIRouter groups related endpoints together.
# The prefix means all routes here start with /api
router = APIRouter(prefix="/api")

# Shared service instance
# In a production app, you'd use FastAPI's dependency injection (Depends())
# but for learning clarity, a module-level singleton works fine.
analysis_service = AnalysisService()


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_pr(pr_input: PRInput):
    """
    Submit code for security analysis.

    Accepts either:
    - diff_text: Raw code/diff to analyze directly
    - pr_url: GitHub PR URL (implemented in Phase 3)

    HOW FASTAPI HANDLES THIS:
    1. Receives JSON POST body
    2. Validates it against PRInput schema (checks types, required fields)
    3. If validation fails → automatic 422 error with details
    4. If valid → calls this function with parsed data
    5. Validates the return value against AnalysisResult schema
    6. Serializes to JSON and sends response

    You get all this validation for FREE just by using type hints.
    """
    # For now, we support diff_text only (PR URL comes in Phase 3)
    if not pr_input.diff_text and not pr_input.pr_url:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'diff_text' or 'pr_url'"
        )

    if pr_input.pr_url:
        # Phase 3: Will parse URL and fetch from GitHub
        raise HTTPException(
            status_code=501,
            detail="GitHub PR URL support coming in Phase 3. Use 'diff_text' for now."
        )

    result = await analysis_service.analyze_diff(pr_input.diff_text)
    return result


@router.get("/analysis/{analysis_id}", response_model=AnalysisResult)
async def get_analysis(analysis_id: str):
    """
    Retrieve a previous analysis by its ID.

    WHY this endpoint?
    Analysis can take 10-30 seconds. In the future (Phase 3),
    the frontend will:
    1. POST /api/analyze → get back analysis_id immediately
    2. Connect to WebSocket for real-time updates
    3. GET /api/analysis/{id} to fetch the final result

    For now, /analyze is synchronous (waits for completion),
    but this endpoint is ready for when we go async.
    """
    result = analysis_service.get_result(analysis_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis '{analysis_id}' not found"
        )
    return result


@router.get("/history")
async def get_history(limit: int = 20):
    """
    Get recent analysis results.

    Query params:
        limit: Max results to return (default 20)

    This powers the dashboard view in the frontend (Phase 3).
    """
    results = analysis_service.get_history(limit=limit)
    return {
        "count": len(results),
        "results": results,
    }


@router.get("/health")
async def health_check():
    """
    System health check.

    Returns status of:
    - Ollama connection
    - Available models
    - Which agents are ready

    Useful for:
    - Frontend: show "system ready" indicator
    - Monitoring: alert if Ollama goes down
    - Debugging: quickly see what's available
    """
    health = await analysis_service.check_health()
    return health
