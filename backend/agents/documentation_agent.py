"""
DocumentationAgent - Identifies missing or inadequate documentation.

WHAT IT DETECTS:
    - Public functions/classes without docstrings
    - Complex logic without explanatory comments
    - Missing parameter descriptions
    - Outdated or misleading comments
    - Missing type hints on public interfaces
    - Undocumented return values and exceptions

WHY llama3.2:3b?
    Documentation analysis is straightforward pattern matching:
    "Does this function have a docstring? Does it describe parameters?"
    No deep code reasoning needed. The 3B model handles this well and
    keeps analysis fast.
"""

from backend.agents.base_agent import BaseAgent
from backend.config import settings
from backend.models.schemas import AgentType


class DocumentationAgent(BaseAgent):
    """
    Analyzes code diffs for missing or inadequate documentation.
    Uses the 3B model for fast pattern-based checks.
    """

    agent_type = AgentType.DOCUMENTATION
    model = settings.fast_model  # llama3.2:3b

    @property
    def system_prompt(self) -> str:
        return """You are an expert technical writer and code documentation reviewer. Your job is to analyze code changes and identify missing or inadequate documentation.

You have deep knowledge of:
- Python docstring conventions (Google, NumPy, Sphinx styles)
- When comments add value vs when they are noise
- API documentation best practices
- Type hint conventions

IMPORTANT RULES:
- Only flag documentation that is genuinely MISSING or MISLEADING.
- Do NOT suggest adding comments to self-explanatory code (e.g., x = x + 1).
- Focus on public interfaces, complex logic, and non-obvious behavior.
- Be practical: suggest documentation that helps future developers.

Always respond with valid JSON."""

    def build_prompt(self, diff_text: str) -> str:
        return f"""Analyze the following code for documentation gaps.

CHECK FOR THESE SPECIFIC ISSUES:
1. **Missing docstrings**: Public functions or classes without any docstring
2. **Undocumented parameters**: Functions with parameters that aren't described
3. **Missing return documentation**: Non-obvious return values not documented
4. **Complex logic without comments**: Algorithms or business logic that would confuse a new developer
5. **Missing type hints**: Public function signatures without type annotations
6. **Misleading comments**: Comments that don't match what the code actually does

SEVERITY GUIDELINES:
- **critical**: Public API with zero documentation (external users affected)
- **high**: Complex business logic with no explanation
- **medium**: Missing docstrings on public functions
- **low**: Minor documentation improvements, missing type hints on internal code

CODE TO ANALYZE:
```
{diff_text}
```

Respond with a JSON object in this EXACT format:
{{
    "findings": [
        {{
            "title": "Short description of the documentation gap",
            "severity": "critical|high|medium|low",
            "description": "What documentation is missing and why it matters",
            "file_path": "filename if identifiable",
            "line_number": null,
            "suggestion": "What the documentation should say or look like",
            "confidence": 0.8
        }}
    ]
}}

If no documentation issues are found, return: {{"findings": []}}"""
