"""
Pydantic schemas for the PR Review AI system.

WHY Pydantic?
When working with LLMs, data flows through many stages:
  User Input → API → Agents → LLM → Parse Response → API → User

At each boundary, things can go wrong. Pydantic validates data at every step,
catching errors early with clear messages instead of mysterious crashes later.

These schemas define the "contract" between all parts of the system.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# Enums - Named constants instead of magic strings
# ============================================================

class Severity(str, Enum):
    """
    How serious is a finding?

    Using an enum instead of raw strings prevents typos like "hihg" or "Critcal"
    and gives us autocomplete in IDEs.
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentType(str, Enum):
    """Each specialized agent in our system."""
    SECURITY = "security"
    PERFORMANCE = "performance"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    STANDARDS = "standards"


class AnalysisStatus(str, Enum):
    """Tracks where an analysis is in its lifecycle."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================
# Core Data Models
# ============================================================

class Finding(BaseModel):
    """
    A single issue found by an agent.

    This is the core output unit - every agent produces a list of these.
    The structured format makes it easy to display, filter, and sort in the UI.
    """
    agent: AgentType = Field(description="Which agent found this issue")
    severity: Severity = Field(description="How serious is this issue")
    title: str = Field(description="Short description, e.g. 'SQL Injection Risk'")
    description: str = Field(description="Detailed explanation of the issue")
    file_path: Optional[str] = Field(default=None, description="Which file has the issue")
    line_number: Optional[int] = Field(default=None, description="Line number in the file")
    suggestion: Optional[str] = Field(default=None, description="How to fix the issue")
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="How confident the agent is (0.0 to 1.0)"
    )


class FileChange(BaseModel):
    """Represents a single file changed in a PR."""
    filename: str
    status: str = Field(description="added, modified, removed, renamed")
    additions: int = 0
    deletions: int = 0
    patch: str = Field(default="", description="The unified diff content")


class PRData(BaseModel):
    """
    All data about a Pull Request that agents need to analyze.

    This is the INPUT to our agent system. We fetch this from GitHub
    and pass it to each agent.
    """
    owner: str = Field(description="GitHub repo owner, e.g. 'facebook'")
    repo: str = Field(description="GitHub repo name, e.g. 'react'")
    pr_number: int = Field(description="PR number, e.g. 12345")
    title: str = Field(default="")
    description: str = Field(default="")
    author: str = Field(default="")
    files: list[FileChange] = Field(default_factory=list)
    raw_diff: str = Field(default="", description="The full unified diff text")


# ============================================================
# API Request/Response Models
# ============================================================

class PRInput(BaseModel):
    """
    What the user sends to our API.

    They can either provide a GitHub PR URL (which we'll parse and fetch)
    or paste raw diff text directly (useful for testing without GitHub).
    """
    pr_url: Optional[str] = Field(
        default=None,
        description="GitHub PR URL, e.g. https://github.com/owner/repo/pull/123"
    )
    diff_text: Optional[str] = Field(
        default=None,
        description="Raw diff text (alternative to PR URL for testing)"
    )


class AgentResult(BaseModel):
    """
    Output from a single agent's analysis.

    Each agent returns one of these. The orchestrator collects all of them
    and combines them into the final AnalysisResult.
    """
    agent: AgentType
    status: AnalysisStatus
    findings: list[Finding] = Field(default_factory=list)
    execution_time: float = Field(default=0.0, description="Seconds taken")
    model_used: str = Field(default="", description="Which LLM model was used")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class AnalysisResult(BaseModel):
    """
    The complete analysis result combining all agents.

    This is the OUTPUT of our system - what the user sees in the UI.
    """
    id: str = Field(description="Unique analysis ID")
    pr_data: PRData
    agent_results: list[AgentResult] = Field(default_factory=list)
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    total_execution_time: float = 0.0
    status: AnalysisStatus = AnalysisStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)


# ============================================================
# WebSocket Event Models (for real-time updates)
# ============================================================

class AgentEvent(BaseModel):
    """
    Real-time event sent over WebSocket to the frontend.

    As agents work, they emit events so the UI can show live progress.
    This is what makes the demo visually impressive - the user sees
    each agent activate, think, and report findings in real-time.
    """
    event_type: str = Field(description="agent_started, agent_thinking, agent_completed, etc.")
    agent: AgentType
    message: str = Field(default="")
    data: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.now)
