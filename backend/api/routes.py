"""
API Routes - HTTP endpoints for the PR Review system.

ENDPOINTS:
    POST /api/analyze         -> Submit code or PR URL for analysis
    GET  /api/analysis/{id}   -> Get results by ID
    GET  /api/history         -> List recent analyses
    GET  /api/health          -> System health check
"""

from fastapi import APIRouter, HTTPException

from backend.models.schemas import AnalysisResult, PRInput
from backend.services.analysis_service import AnalysisService
from backend.services.github_service import GitHubService

router = APIRouter(prefix="/api")

analysis_service = AnalysisService()
github_service = GitHubService()


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_pr(pr_input: PRInput):
    """
    Submit code for multi-agent analysis.

    Accepts either:
    - diff_text: Raw code/diff to analyze directly
    - pr_url: GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)
    """
    if not pr_input.diff_text and not pr_input.pr_url:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'diff_text' or 'pr_url'"
        )

    if pr_input.pr_url:
        try:
            pr_data = await github_service.fetch_pr_from_url(pr_input.pr_url)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except PermissionError as e:
            raise HTTPException(status_code=429, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch PR: {e}")

        if not pr_data.raw_diff:
            raise HTTPException(
                status_code=400,
                detail="PR has no code changes (empty diff)"
            )

        result = await analysis_service.analyze_diff(pr_data.raw_diff, pr_data=pr_data)
    else:
        result = await analysis_service.analyze_diff(pr_input.diff_text)

    return result


@router.get("/analysis/{analysis_id}", response_model=AnalysisResult)
async def get_analysis(analysis_id: str):
    """Retrieve a previous analysis by its ID."""
    result = analysis_service.get_result(analysis_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis '{analysis_id}' not found"
        )
    return result


@router.get("/history")
async def get_history(limit: int = 20):
    """Get recent analysis results, newest first."""
    results = analysis_service.get_history(limit=limit)
    return {
        "count": len(results),
        "results": results,
    }


@router.get("/health")
async def health_check():
    """System health check — Ollama, models, agents status."""
    health = await analysis_service.check_health()
    return health
