"""
Analysis Service - Coordinates agent execution for PR reviews.

WHY a service layer between the API and the agents?
This is the "Separation of Concerns" principle:

    API Routes (api/routes.py)
        -> Handle HTTP: parse requests, format responses, status codes
        -> Should NOT know how agents work

    Analysis Service (this file)
        -> Business logic: which agents to run, how to combine results
        -> Knows about agents but NOT about HTTP

    Agents (agents/*.py)
        -> Domain logic: analyze code for specific issues
        -> Know nothing about HTTP or the service layer

PHASE 2 UPDATE:
    Now uses the LangGraph orchestrator to run all 5 agents in parallel.
    The orchestrator handles fan-out (dispatching to agents), parallel
    execution, and aggregation (combining results).
"""

from typing import Optional

from backend.agents.orchestrator import PRReviewOrchestrator
from backend.models.ollama_client import OllamaClient
from backend.models.schemas import (
    AnalysisResult,
    PRData,
)


class AnalysisService:
    """
    Coordinates PR analysis using the LangGraph orchestrator.

    Phase 1: Ran only SecurityAgent directly
    Phase 2: Runs all 5 agents in parallel via LangGraph orchestrator
    """

    def __init__(self):
        self.client = OllamaClient()
        self.orchestrator = PRReviewOrchestrator(ollama_client=self.client)

        # In-memory store for analysis results
        # Phase 4 will replace this with PostgreSQL
        self._results: dict[str, AnalysisResult] = {}

    async def analyze_diff(self, diff_text: str, pr_data: Optional[PRData] = None) -> AnalysisResult:
        """
        Run all agents on a code diff via the LangGraph orchestrator.

        Args:
            diff_text: The code to analyze (raw diff or source code)
            pr_data: Optional PR metadata (owner, repo, PR number, etc.)

        Returns:
            AnalysisResult with combined findings from all 5 agents.

        WHAT HAPPENS:
            1. Orchestrator fans out diff_text to all 5 agents in parallel
            2. Each agent analyzes independently (Security, Performance,
               Testing, Documentation, Standards)
            3. Results are aggregated into a single AnalysisResult
            4. Stored in memory for retrieval via GET /api/analysis/{id}
        """
        result = await self.orchestrator.run(diff_text, pr_data=pr_data)

        # Store for later retrieval
        self._results[result.id] = result

        return result

    def get_result(self, analysis_id: str) -> Optional[AnalysisResult]:
        """Retrieve a previous analysis result by ID."""
        return self._results.get(analysis_id)

    def get_history(self, limit: int = 20) -> list[AnalysisResult]:
        """Get recent analysis results, newest first."""
        results = list(self._results.values())
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results[:limit]

    async def check_health(self) -> dict:
        """
        Check if the system is ready (Ollama running, models available).

        This powers the /health endpoint - useful for monitoring
        and for the frontend to know if the backend is ready.
        """
        health = {
            "status": "healthy",
            "ollama_connected": False,
            "models_available": [],
            "agents_ready": [],
        }

        try:
            await self.client.check_connection()
            health["ollama_connected"] = True

            models = await self.client.list_models()
            health["models_available"] = [m["name"] for m in models]

            # Check which agents have their required models
            for name, agent in self.orchestrator.agents.items():
                if await self.client.check_model_available(agent.model):
                    health["agents_ready"].append(name)

        except Exception as e:
            health["status"] = "degraded"
            health["error"] = str(e)

        return health
