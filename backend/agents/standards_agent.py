"""
StandardsAgent - Checks code style, naming conventions, and best practices.

WHAT IT DETECTS:
    - Inconsistent naming conventions (camelCase vs snake_case)
    - Magic numbers without named constants
    - Functions that are too long or do too many things
    - Deeply nested code (arrow anti-pattern)
    - Unused imports or variables
    - Inconsistent error handling patterns
    - Code duplication

WHY llama3.2:3b?
    Style and convention checking is pure pattern matching — the simplest
    analysis type. "Is this variable snake_case?" doesn't need a 7B model.
    Using the 3B model here means this agent completes in ~2 seconds,
    which keeps the overall multi-agent analysis fast.
"""

from backend.agents.base_agent import BaseAgent
from backend.config import settings
from backend.models.schemas import AgentType


class StandardsAgent(BaseAgent):
    """
    Analyzes code diffs for style, convention, and best practice violations.
    Uses the 3B model for fast pattern-based analysis.
    """

    agent_type = AgentType.STANDARDS
    model = settings.fast_model  # llama3.2:3b

    @property
    def system_prompt(self) -> str:
        return """You are an expert code reviewer focused on code quality, style, and best practices. Your job is to analyze code changes for convention violations and maintainability issues.

You have deep knowledge of:
- PEP 8 (Python style guide)
- Clean Code principles
- SOLID design principles
- Common code smells and anti-patterns

IMPORTANT RULES:
- Focus on issues that affect readability and maintainability.
- Do NOT nitpick formatting that an auto-formatter would handle (spacing, line length).
- Be practical: flag issues that would cause confusion or bugs in a team setting.
- Respect existing project conventions even if they differ from your preference.

Always respond with valid JSON."""

    def build_prompt(self, diff_text: str) -> str:
        return f"""Analyze the following code for coding standards and best practice violations.

CHECK FOR THESE SPECIFIC ISSUES:
1. **Naming conventions**: Inconsistent style (mixing camelCase and snake_case), unclear variable names
2. **Magic numbers**: Hardcoded numeric values without named constants
3. **Function complexity**: Functions doing too many things, too many parameters (>5), too long (>50 lines)
4. **Deep nesting**: More than 3 levels of indentation (if/for/if/for)
5. **Code duplication**: Repeated logic that should be extracted into a function
6. **Error handling**: Bare except clauses, swallowing exceptions silently, inconsistent patterns
7. **Dead code**: Unused imports, unreachable code, commented-out code blocks

SEVERITY GUIDELINES:
- **critical**: Naming or patterns so confusing they will cause bugs
- **high**: Significant maintainability issue, code is hard to understand or modify
- **medium**: Convention violation that reduces readability
- **low**: Minor style issue, nice-to-have improvement

CODE TO ANALYZE:
```
{diff_text}
```

Respond with a JSON object in this EXACT format:
{{
    "findings": [
        {{
            "title": "Short description of the standards violation",
            "severity": "critical|high|medium|low",
            "description": "What the issue is and why it matters for maintainability",
            "file_path": "filename if identifiable",
            "line_number": null,
            "suggestion": "How to fix it with a concrete example",
            "confidence": 0.8
        }}
    ]
}}

If no standards issues are found, return: {{"findings": []}}"""
