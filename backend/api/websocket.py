"""
WebSocket endpoint for real-time agent activity streaming.

WHY WEBSOCKET instead of plain HTTP?

    HTTP (request/response):
        Client: "Are you done yet?" -> Server: "No"
        Client: "Are you done yet?" -> Server: "No"
        Client: "Are you done yet?" -> Server: "Yes, here are results"
        (Polling = wasteful, laggy)

    WebSocket (persistent connection):
        Client: "Start analysis"
        Server: "Security agent started..."
        Server: "Security agent found 2 issues..."
        Server: "Performance agent started..."
        Server: "Performance agent found 3 issues..."
        Server: "All done! Here's the full result."
        (Real-time, efficient, impressive for demos)

HOW IT WORKS:
    1. Frontend opens WebSocket to /ws/analyze
    2. Frontend sends {"diff_text": "..."} or {"pr_url": "..."}
    3. Backend starts analysis and streams events as agents work
    4. Each event is a JSON message with type, agent name, and data
    5. When all agents finish, sends final result and closes
"""

import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from backend.models.schemas import PRInput
from backend.services.github_service import GitHubService


class ConnectionManager:
    """
    Manages active WebSocket connections.

    Tracks connected clients so we can:
    - Send events to specific sessions
    - Clean up when clients disconnect
    - (Future) broadcast to multiple viewers of the same analysis
    """

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)

    async def send_event(self, session_id: str, event: dict):
        """Send a JSON event to a specific client."""
        ws = self.active_connections.get(session_id)
        if ws:
            await ws.send_json(event)


manager = ConnectionManager()


def make_event(event_type: str, agent: Optional[str] = None,
               message: str = "", data: Optional[dict] = None) -> dict:
    """Create a structured WebSocket event."""
    return {
        "event_type": event_type,
        "agent": agent,
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat(),
    }


async def handle_analysis(websocket: WebSocket, session_id: str):
    """
    Handle a WebSocket analysis session.

    Flow:
    1. Receive input (diff_text or pr_url)
    2. If pr_url, fetch from GitHub (with progress events)
    3. Run agents via orchestrator (with per-agent events)
    4. Send final result
    """
    from backend.agents.orchestrator import PRReviewOrchestrator
    from backend.models.ollama_client import OllamaClient
    from backend.models.schemas import PRData

    github_service = GitHubService()

    try:
        # Step 1: Receive input
        raw_data = await websocket.receive_text()
        input_data = json.loads(raw_data)

        pr_url = input_data.get("pr_url")
        diff_text = input_data.get("diff_text")
        pr_data = None

        if not pr_url and not diff_text:
            await manager.send_event(session_id, make_event(
                "error", message="Provide either 'diff_text' or 'pr_url'"
            ))
            return

        # Step 2: Fetch PR if URL provided
        if pr_url:
            await manager.send_event(session_id, make_event(
                "fetch_started", message=f"Fetching PR from {pr_url}..."
            ))

            try:
                pr_data = await github_service.fetch_pr_from_url(pr_url)
                diff_text = pr_data.raw_diff

                await manager.send_event(session_id, make_event(
                    "fetch_completed",
                    message=f"Fetched PR #{pr_data.pr_number}: {pr_data.title}",
                    data={
                        "title": pr_data.title,
                        "author": pr_data.author,
                        "files_changed": len(pr_data.files),
                    }
                ))
            except Exception as e:
                await manager.send_event(session_id, make_event(
                    "error", message=f"Failed to fetch PR: {e}"
                ))
                return

        if not diff_text:
            await manager.send_event(session_id, make_event(
                "error", message="PR has no code changes"
            ))
            return

        # Step 3: Run agents with progress events
        await manager.send_event(session_id, make_event(
            "analysis_started",
            message="Starting multi-agent analysis...",
            data={"agents": ["security", "performance", "testing", "documentation", "standards"]}
        ))

        client = OllamaClient()
        orchestrator = PRReviewOrchestrator(ollama_client=client)

        # Run each agent and stream events as they complete
        # We run them as individual tasks so we can report progress
        agents_config = [
            ("security", orchestrator.agents["security"]),
            ("performance", orchestrator.agents["performance"]),
            ("testing", orchestrator.agents["testing"]),
            ("documentation", orchestrator.agents["documentation"]),
            ("standards", orchestrator.agents["standards"]),
        ]

        # Notify all agents starting
        for name, _ in agents_config:
            await manager.send_event(session_id, make_event(
                "agent_started", agent=name,
                message=f"{name.title()} agent analyzing..."
            ))

        # Run all agents in parallel, reporting as each completes
        async def run_and_report(name, agent):
            result = await agent.analyze(diff_text)
            await manager.send_event(session_id, make_event(
                "agent_completed", agent=name,
                message=f"{name.title()} agent found {len(result.findings)} issues",
                data={
                    "findings_count": len(result.findings),
                    "execution_time": result.execution_time,
                    "status": result.status.value,
                }
            ))
            return result

        agent_results = await asyncio.gather(
            *[run_and_report(name, agent) for name, agent in agents_config]
        )

        # Step 4: Aggregate and send final result
        from backend.models.schemas import AnalysisResult, AnalysisStatus, Severity
        import uuid

        all_findings = []
        for ar in agent_results:
            all_findings.extend(ar.findings)

        if pr_data is None:
            pr_data = PRData(
                owner="local", repo="paste", pr_number=0,
                title="Direct diff analysis", raw_diff=diff_text,
            )

        final_result = AnalysisResult(
            id=str(uuid.uuid4())[:8],
            pr_data=pr_data,
            agent_results=list(agent_results),
            total_findings=len(all_findings),
            critical_count=sum(1 for f in all_findings if f.severity == Severity.CRITICAL),
            high_count=sum(1 for f in all_findings if f.severity == Severity.HIGH),
            medium_count=sum(1 for f in all_findings if f.severity == Severity.MEDIUM),
            low_count=sum(1 for f in all_findings if f.severity == Severity.LOW),
            total_execution_time=round(max(
                (ar.execution_time for ar in agent_results), default=0
            ), 2),
            status=AnalysisStatus.COMPLETED,
        )

        await manager.send_event(session_id, make_event(
            "analysis_completed",
            message=f"Analysis complete: {final_result.total_findings} findings",
            data=final_result.model_dump(mode="json"),
        ))

        await client.close()

    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        await manager.send_event(session_id, make_event(
            "error", message="Invalid JSON input"
        ))
    except Exception as e:
        await manager.send_event(session_id, make_event(
            "error", message=f"Analysis failed: {e}"
        ))
