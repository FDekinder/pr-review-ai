"""
BaseAgent - Abstract base class for all PR review agents.

WHY an abstract base class?
This is the Strategy Pattern in action. All our agents (Security, Performance,
Testing, etc.) share the same workflow:

    1. Receive code diff
    2. Build a specialized prompt
    3. Call the LLM
    4. Parse the response into structured findings
    5. Return typed results with metadata

What DIFFERS between agents:
    - The system prompt (their "expertise")
    - The analysis prompt (what they look for)
    - The model they use (3B for simple tasks, 7B for complex)

By putting shared logic here, each agent only needs ~50 lines of code
to define its unique behavior. This is what makes the system extensible -
adding a new agent takes minutes, not hours.

DESIGN DECISIONS:
    - async by default: Agents will run in parallel via asyncio.gather()
    - JSON output: All agents return structured data, never raw text
    - Confidence scoring: Agents report how confident they are
    - Graceful failure: If the LLM returns garbage, the agent doesn't crash
"""

import time
from abc import ABC, abstractmethod
from typing import Optional

from backend.config import settings
from backend.models.ollama_client import OllamaClient
from backend.models.schemas import (
    AgentResult,
    AgentType,
    AnalysisStatus,
    Finding,
    Severity,
)


class BaseAgent(ABC):
    """
    Abstract base class that all review agents inherit from.

    To create a new agent, subclass this and implement:
        1. agent_type: What kind of agent this is
        2. model: Which LLM to use
        3. system_prompt: The agent's expertise/personality
        4. build_prompt(): How to construct the analysis prompt
        5. parse_response(): How to interpret the LLM's response
    """

    # Subclasses MUST override these
    agent_type: AgentType
    model: str

    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        """
        Initialize with an Ollama client.

        WHY accept the client as a parameter?
        Dependency Injection - instead of creating the client internally,
        we accept it from outside. This lets us:
        1. Share one client across all agents (efficient)
        2. Inject a mock client in tests (testable)
        3. Configure the client once, use everywhere (clean)
        """
        self.client = ollama_client or OllamaClient()

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """
        The agent's identity and expertise.

        This is like giving the LLM a "job description". It tells the model:
        - What role it plays
        - What to focus on
        - How to structure its response
        - What format to use

        Good system prompts are the #1 factor in agent quality.
        """
        ...

    @abstractmethod
    def build_prompt(self, diff_text: str) -> str:
        """
        Build the analysis prompt from the code diff.

        Each agent asks different questions about the same code.
        The Security agent asks "what vulnerabilities exist?"
        The Performance agent asks "what's slow?"
        """
        ...

    def parse_response(self, data: dict) -> list[Finding]:
        """
        Convert the LLM's JSON response into typed Finding objects.

        Default implementation handles the common format:
        {"findings": [{"title": "...", "severity": "...", ...}]}

        Agents can override this if they need custom parsing.

        WHY is this needed?
        LLMs are unpredictable. Even with JSON mode, they might:
        - Use different key names ("issues" vs "findings" vs "problems")
        - Return severity as "HIGH" vs "high" vs "High"
        - Omit optional fields
        - Add unexpected fields

        This method normalizes all of that into clean Finding objects.
        """
        findings = []
        raw_findings = data.get("findings", data.get("issues", []))

        if not isinstance(raw_findings, list):
            return findings

        for item in raw_findings:
            if not isinstance(item, dict):
                continue

            try:
                severity_str = item.get("severity", "medium").lower().strip()
                try:
                    severity = Severity(severity_str)
                except ValueError:
                    # LLM might say "critical!" or "HIGH" - normalize it
                    severity_map = {
                        "critical": Severity.CRITICAL,
                        "high": Severity.HIGH,
                        "medium": Severity.MEDIUM,
                        "low": Severity.LOW,
                        "info": Severity.LOW,
                    }
                    severity = severity_map.get(severity_str, Severity.MEDIUM)

                # Normalize fields that LLMs sometimes return as lists
                suggestion_raw = item.get("suggestion") or item.get("fix")
                if isinstance(suggestion_raw, list):
                    suggestion_raw = "; ".join(str(s) for s in suggestion_raw)

                description_raw = item.get("description", "No description provided")
                if isinstance(description_raw, list):
                    description_raw = " ".join(str(s) for s in description_raw)

                finding = Finding(
                    agent=self.agent_type,
                    severity=severity,
                    title=item.get("title", "Untitled Finding"),
                    description=description_raw,
                    file_path=item.get("file_path") or item.get("file"),
                    line_number=item.get("line_number") or item.get("line"),
                    suggestion=suggestion_raw,
                    confidence=float(item.get("confidence", 0.8)),
                )
                findings.append(finding)

            except Exception as e:
                # If one finding fails to parse, skip it and continue
                # Don't let one bad finding kill the entire analysis
                print(f"[{self.agent_type.value}] Failed to parse finding: {e}")
                continue

        return findings

    async def analyze(self, diff_text: str) -> AgentResult:
        """
        Run the full analysis pipeline.

        This is the main entry point. The orchestrator calls this method
        on each agent, passing the same diff_text. Each agent analyzes
        it through its own lens and returns its findings.

        Pipeline:
            1. Build the prompt (agent-specific)
            2. Call the LLM with JSON output
            3. Parse the response into Findings
            4. Wrap everything in an AgentResult with metadata
            5. Handle any errors gracefully

        Returns AgentResult which includes:
            - The findings themselves
            - How long the analysis took
            - Which model was used
            - Success/failure status
            - Error message if something went wrong
        """
        start_time = time.time()

        try:
            prompt = self.build_prompt(diff_text)

            result = await self.client.generate_json(
                model=self.model,
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.1,  # Low temperature = consistent, factual analysis
            )

            findings = self.parse_response(result["data"])
            elapsed = time.time() - start_time

            print(f"[{self.agent_type.value}] Found {len(findings)} issues "
                  f"in {elapsed:.1f}s using {self.model}")

            return AgentResult(
                agent=self.agent_type,
                status=AnalysisStatus.COMPLETED,
                findings=findings,
                execution_time=round(elapsed, 2),
                model_used=self.model,
            )

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[{self.agent_type.value}] FAILED after {elapsed:.1f}s: {e}")

            return AgentResult(
                agent=self.agent_type,
                status=AnalysisStatus.FAILED,
                findings=[],
                execution_time=round(elapsed, 2),
                model_used=self.model,
                error=str(e),
            )
