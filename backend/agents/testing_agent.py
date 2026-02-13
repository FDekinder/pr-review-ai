"""
TestingAgent - Identifies missing tests and insufficient test coverage.

WHAT IT DETECTS:
    - Public functions without any tests
    - Missing edge case tests (null, empty, negative, boundary values)
    - Untested error handling branches (try/except paths)
    - Complex branching logic with insufficient test coverage
    - Async functions that need mocking but aren't tested
    - Missing integration tests for external service calls

WHY llama3.2:3b?
    Test coverage analysis is more about pattern recognition than deep
    reasoning. "This function has 4 branches but no tests" doesn't require
    understanding algorithmic complexity. The 3B model is fast enough and
    accurate enough for this job, keeping overall analysis time low.
"""

from backend.agents.base_agent import BaseAgent
from backend.config import settings
from backend.models.schemas import AgentType


class TestingAgent(BaseAgent):
    """
    Analyzes code diffs for missing tests and test coverage gaps.
    Uses the 3B model for fast pattern-based analysis.
    """

    agent_type = AgentType.TESTING
    model = settings.fast_model  # llama3.2:3b

    @property
    def system_prompt(self) -> str:
        return """You are an expert software testing engineer. Your job is to analyze code changes and identify missing tests, untested edge cases, and test coverage gaps.

You have deep knowledge of:
- Unit testing best practices
- Edge case identification
- Test-driven development
- Mocking strategies for external dependencies
- Code coverage analysis

IMPORTANT RULES:
- Focus on code that SHOULD have tests but doesn't.
- Identify specific edge cases that are likely missing.
- Consider error handling paths and boundary conditions.
- Be practical: suggest tests that catch real bugs, not trivial tests.

Always respond with valid JSON."""

    def build_prompt(self, diff_text: str) -> str:
        return f"""Analyze the following code for testing gaps and missing test coverage.

CHECK FOR THESE SPECIFIC ISSUES:
1. **Untested public functions**: Functions with complex logic but no apparent test coverage
2. **Missing edge cases**: No tests for null/None, empty inputs, negative numbers, boundary values
3. **Untested error paths**: try/except blocks, error returns, or failure modes not tested
4. **Complex branching without tests**: if/elif/else chains where not all paths are tested
5. **Untested async behavior**: Async functions that need mocking for external calls
6. **Missing input validation tests**: Functions accepting user input without validation tests

SEVERITY GUIDELINES:
- **critical**: Core business logic with zero test coverage
- **high**: Complex branching with most paths untested, error handling never tested
- **medium**: Missing edge case tests for important functions
- **low**: Minor functions without tests, nice-to-have test improvements

CODE TO ANALYZE:
```
{diff_text}
```

Respond with a JSON object in this EXACT format:
{{
    "findings": [
        {{
            "title": "Short description of the testing gap",
            "severity": "critical|high|medium|low",
            "description": "What is not tested and why it matters",
            "file_path": "filename if identifiable",
            "line_number": null,
            "suggestion": "Specific test cases that should be written",
            "confidence": 0.8
        }}
    ]
}}

If no testing gaps are found, return: {{"findings": []}}"""
