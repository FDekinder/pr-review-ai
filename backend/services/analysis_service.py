"""
Analysis Service - Coordinates agent execution for PR reviews.

WHY a service layer between the API and the agents?
This is the "Separation of Concerns" principle:

    API Routes (api/routes.py)
        → Handle HTTP: parse requests, format responses, status codes
        → Should NOT know how agents work

    Analysis Service (this file)
        → Business logic: which agents to run, how to combine results
        → Knows about agents but NOT about HTTP

    Agents (agents/*.py)
        → Domain logic: analyze code for specific issues
        → Know nothing about HTTP or the service layer

This layering means:
- You can test the service without starting a web server
- You can swap FastAPI for Django without touching agent logic
- You can add new agents without changing the API layer
- Each layer has one clear responsibility
"""

import time
import uuid
from typing import Optional

from backend.agents.security_agent import SecurityAgent
from backend.models.ollama_client import OllamaClient
from backend.models.schemas import (
    AgentResult,
    AnalysisResult,
    AnalysisStatus,
    PRData,
    Severity,
)


class AnalysisService:
    """
    Coordinates PR analysis across all agents.

    Currently runs only the SecurityAgent (Phase 1.3).
    In Phase 2, this will run all 5 agents in parallel via LangGraph.
    """

    def __init__(self):
        self.client = OllamaClient()

        # Initialize available agents
        # Phase 1: Just the SecurityAgent
        # Phase 2: Will add Performance, Testing, Documentation, Standards
        self.security_agent = SecurityAgent(ollama_client=self.client)

        # In-memory store for analysis results
        # Phase 4 will replace this with PostgreSQL
        self._results: dict[str, AnalysisResult] = {}

    async def analyze_diff(self, diff_text: str, pr_data: Optional[PRData] = None) -> AnalysisResult:
        """
        Run all available agents on a code diff.

        Args:
            diff_text: The code to analyze (raw diff or source code)
            pr_data: Optional PR metadata (owner, repo, PR number, etc.)

        Returns:
            AnalysisResult with combined findings from all agents.

        WHAT HAPPENS HERE (Phase 1):
            1. Create a unique analysis ID
            2. Run SecurityAgent on the diff
            3. Combine results into AnalysisResult
            4. Store in memory for retrieval

        WHAT WILL HAPPEN (Phase 2 - LangGraph):
            1. Triage agent decides which agents to run
            2. Agents run IN PARALLEL via asyncio.gather()
            3. Aggregator combines and deduplicates findings
            4. Results stream via WebSocket in real-time
        """
        analysis_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Default PR data if not provided (e.g., for raw diff analysis)
        if pr_data is None:
            pr_data = PRData(
                owner="local",
                repo="paste",
                pr_number=0,
                title="Direct diff analysis",
                raw_diff=diff_text,
            )

        # Create initial result (status: in_progress)
        result = AnalysisResult(
            id=analysis_id,
            pr_data=pr_data,
            status=AnalysisStatus.IN_PROGRESS,
        )
        self._results[analysis_id] = result

        # Run agents
        # Phase 1: Just security (sequential)
        # Phase 2: All agents in parallel with asyncio.gather()
        agent_results: list[AgentResult] = []

        security_result = await self.security_agent.analyze(diff_text)
        agent_results.append(security_result)

        # TODO Phase 2: Add parallel agent execution
        # agent_results = await asyncio.gather(
        #     self.security_agent.analyze(diff_text),
        #     self.performance_agent.analyze(diff_text),
        #     self.testing_agent.analyze(diff_text),
        #     self.documentation_agent.analyze(diff_text),
        #     self.standards_agent.analyze(diff_text),
        # )

        # Combine results
        total_time = time.time() - start_time
        all_findings = []
        for ar in agent_results:
            all_findings.extend(ar.findings)

        result.agent_results = agent_results
        result.total_findings = len(all_findings)
        result.critical_count = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
        result.high_count = sum(1 for f in all_findings if f.severity == Severity.HIGH)
        result.medium_count = sum(1 for f in all_findings if f.severity == Severity.MEDIUM)
        result.low_count = sum(1 for f in all_findings if f.severity == Severity.LOW)
        result.total_execution_time = round(total_time, 2)
        result.status = AnalysisStatus.COMPLETED

        # Update stored result
        self._results[analysis_id] = result

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
            if await self.client.check_model_available(self.security_agent.model):
                health["agents_ready"].append("security")

        except Exception as e:
            health["status"] = "degraded"
            health["error"] = str(e)

        return health
