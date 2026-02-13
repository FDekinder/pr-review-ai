"""
Unit tests for the PR Review agents.

TESTING AI SYSTEMS - KEY CHALLENGE:
LLM outputs are non-deterministic. The same prompt can produce slightly
different responses each time. So how do you write reliable tests?

Strategy:
1. Mock tests (fast, deterministic): Feed the agent a pre-recorded LLM response
   and verify the parsing/validation logic works correctly.
2. Integration tests (slow, real LLM): Run against actual Ollama to verify
   the full pipeline works end-to-end. These are more like smoke tests.

We use BOTH approaches:
- Mock tests run in CI/CD (fast, always pass)
- Integration tests run locally to verify Ollama + agents work together
"""

import pytest
import pytest_asyncio

from backend.agents.base_agent import BaseAgent
from backend.agents.security_agent import SecurityAgent
from backend.models.ollama_client import OllamaClient
from backend.models.schemas import (
    AgentType,
    AnalysisStatus,
    Finding,
    Severity,
)


# ============================================================
# Mock Ollama Client for deterministic tests
# ============================================================

class MockOllamaClient(OllamaClient):
    """
    A fake Ollama client that returns pre-defined responses.

    WHY MOCK?
    - Tests run instantly (no waiting for LLM inference)
    - Tests are deterministic (same input = same output every time)
    - Tests work without Ollama installed (CI/CD environments)
    - We can test edge cases (malformed responses, errors, etc.)
    """

    def __init__(self, mock_response: dict | None = None, should_fail: bool = False):
        self.mock_response = mock_response or {}
        self.should_fail = should_fail
        # Don't call super().__init__() - we don't need a real HTTP client

    async def generate_json(self, model, prompt, system_prompt=None, temperature=0.1):
        if self.should_fail:
            raise ConnectionError("Mock connection failure")

        return {
            "data": self.mock_response,
            "model": model,
            "elapsed_seconds": 0.1,
            "eval_count": 100,
        }

    async def close(self):
        pass


# ============================================================
# Test: Response Parsing (deterministic)
# ============================================================

class TestSecurityAgentParsing:
    """Test that the agent correctly parses LLM responses into Findings."""

    @pytest.mark.asyncio
    async def test_parses_valid_findings(self):
        """Agent should convert well-formed JSON into Finding objects."""
        mock_response = {
            "findings": [
                {
                    "title": "SQL Injection",
                    "severity": "critical",
                    "description": "User input in SQL query",
                    "suggestion": "Use parameterized queries",
                    "confidence": 0.95,
                },
                {
                    "title": "Hardcoded Secret",
                    "severity": "high",
                    "description": "API key in source code",
                    "suggestion": "Use environment variables",
                    "confidence": 0.9,
                },
            ]
        }

        agent = SecurityAgent(ollama_client=MockOllamaClient(mock_response))
        result = await agent.analyze("some code diff")

        assert result.status == AnalysisStatus.COMPLETED
        assert len(result.findings) == 2
        assert result.findings[0].title == "SQL Injection"
        assert result.findings[0].severity == Severity.CRITICAL
        assert result.findings[0].agent == AgentType.SECURITY
        assert result.findings[1].severity == Severity.HIGH

    @pytest.mark.asyncio
    async def test_handles_empty_findings(self):
        """Agent should handle clean code (no vulnerabilities) gracefully."""
        mock_response = {"findings": []}

        agent = SecurityAgent(ollama_client=MockOllamaClient(mock_response))
        result = await agent.analyze("clean code with no issues")

        assert result.status == AnalysisStatus.COMPLETED
        assert len(result.findings) == 0

    @pytest.mark.asyncio
    async def test_handles_alternative_key_names(self):
        """LLMs sometimes use 'issues' instead of 'findings' - handle both."""
        mock_response = {
            "issues": [
                {
                    "title": "XSS Vulnerability",
                    "severity": "high",
                    "description": "Unescaped output",
                }
            ]
        }

        agent = SecurityAgent(ollama_client=MockOllamaClient(mock_response))
        result = await agent.analyze("some code")

        assert len(result.findings) == 1
        assert result.findings[0].title == "XSS Vulnerability"

    @pytest.mark.asyncio
    async def test_normalizes_severity_values(self):
        """LLMs might return 'HIGH' or 'High' instead of 'high'."""
        mock_response = {
            "findings": [
                {"title": "Issue 1", "severity": "HIGH", "description": "test"},
                {"title": "Issue 2", "severity": "Critical", "description": "test"},
                {"title": "Issue 3", "severity": "low", "description": "test"},
            ]
        }

        agent = SecurityAgent(ollama_client=MockOllamaClient(mock_response))
        result = await agent.analyze("code")

        assert result.findings[0].severity == Severity.HIGH
        assert result.findings[1].severity == Severity.CRITICAL
        assert result.findings[2].severity == Severity.LOW

    @pytest.mark.asyncio
    async def test_handles_malformed_finding(self):
        """If one finding is malformed, skip it but keep the rest."""
        mock_response = {
            "findings": [
                {"title": "Good Finding", "severity": "high", "description": "valid"},
                "this is not a dict - should be skipped",
                {"title": "Another Good", "severity": "low", "description": "also valid"},
            ]
        }

        agent = SecurityAgent(ollama_client=MockOllamaClient(mock_response))
        result = await agent.analyze("code")

        # Should have 2 findings (the malformed one is skipped)
        assert len(result.findings) == 2

    @pytest.mark.asyncio
    async def test_default_confidence(self):
        """Findings without explicit confidence should default to 0.8."""
        mock_response = {
            "findings": [
                {"title": "Test", "severity": "medium", "description": "test"},
            ]
        }

        agent = SecurityAgent(ollama_client=MockOllamaClient(mock_response))
        result = await agent.analyze("code")

        assert result.findings[0].confidence == 0.8


# ============================================================
# Test: Error Handling
# ============================================================

class TestAgentErrorHandling:
    """Test that agents handle failures gracefully."""

    @pytest.mark.asyncio
    async def test_handles_connection_failure(self):
        """If Ollama is down, agent should return FAILED status, not crash."""
        agent = SecurityAgent(
            ollama_client=MockOllamaClient(should_fail=True)
        )
        result = await agent.analyze("some code")

        assert result.status == AnalysisStatus.FAILED
        assert result.error is not None
        assert "Mock connection failure" in result.error
        assert len(result.findings) == 0

    @pytest.mark.asyncio
    async def test_failed_result_has_metadata(self):
        """Even failed results should include timing and model info."""
        agent = SecurityAgent(
            ollama_client=MockOllamaClient(should_fail=True)
        )
        result = await agent.analyze("code")

        assert result.agent == AgentType.SECURITY
        assert result.execution_time >= 0
        assert result.model_used == agent.model


# ============================================================
# Test: Agent Identity
# ============================================================

class TestAgentIdentity:
    """Test that agents correctly identify themselves."""

    def test_security_agent_type(self):
        agent = SecurityAgent(ollama_client=MockOllamaClient())
        assert agent.agent_type == AgentType.SECURITY

    def test_security_agent_model(self):
        agent = SecurityAgent(ollama_client=MockOllamaClient())
        assert "coder" in agent.model or "qwen" in agent.model

    def test_security_agent_has_system_prompt(self):
        agent = SecurityAgent(ollama_client=MockOllamaClient())
        assert len(agent.system_prompt) > 100
        assert "security" in agent.system_prompt.lower()


# ============================================================
# Integration Test: Real Ollama (skip if not available)
# ============================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_security_agent_finds_sql_injection():
    """
    Integration test: Run real SecurityAgent against known vulnerable code.

    This test requires Ollama to be running with qwen2.5-coder:7b.
    Skip in CI with: pytest -m "not integration"
    """
    client = OllamaClient()
    try:
        await client.check_connection()
    except ConnectionError:
        pytest.skip("Ollama not running")

    agent = SecurityAgent(ollama_client=client)

    vulnerable_code = '''
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    cursor.execute(query)
    return cursor.fetchone()
'''

    result = await agent.analyze(vulnerable_code)

    assert result.status == AnalysisStatus.COMPLETED
    assert len(result.findings) > 0

    # At least one finding should mention SQL injection
    titles = [f.title.lower() for f in result.findings]
    descriptions = [f.description.lower() for f in result.findings]
    all_text = " ".join(titles + descriptions)
    assert "sql" in all_text or "injection" in all_text

    await client.close()
