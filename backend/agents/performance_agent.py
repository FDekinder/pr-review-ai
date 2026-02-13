"""
PerformanceAgent - Detects performance issues and optimization opportunities.

WHAT IT DETECTS:
    - O(n^2) and higher complexity algorithms
    - N+1 query problems (database)
    - Memory inefficiencies (loading entire files, string concatenation in loops)
    - Blocking calls in async contexts (time.sleep in async functions)
    - Missing caching opportunities
    - Inefficient data structure choices

WHY qwen2.5-coder:7b?
    Performance analysis requires understanding algorithmic complexity and
    data flow patterns. The 7B model can reason about nested loops being O(n^2)
    and understand that repeated database calls inside a loop is an N+1 problem.
    The 3B model would miss these higher-level patterns.
"""

from backend.agents.base_agent import BaseAgent
from backend.config import settings
from backend.models.schemas import AgentType


class PerformanceAgent(BaseAgent):
    """
    Analyzes code diffs for performance issues and optimization opportunities.
    Uses the 7B model for algorithmic complexity reasoning.
    """

    agent_type = AgentType.PERFORMANCE
    model = settings.balanced_model  # qwen2.5-coder:7b

    @property
    def system_prompt(self) -> str:
        return """You are an expert software performance engineer. Your job is to analyze code changes and identify performance bottlenecks, inefficiencies, and optimization opportunities.

You have deep knowledge of:
- Algorithmic complexity (Big O notation)
- Database query optimization (N+1 problems, missing indexes)
- Memory management and efficient data structures
- Async/concurrent programming patterns
- Caching strategies

IMPORTANT RULES:
- Only report REAL performance issues visible in the code. Do NOT hallucinate.
- Focus on issues that would matter at scale (100+ items, 1000+ users).
- Be specific about the complexity and expected impact.
- Suggest concrete fixes, not vague advice.

Always respond with valid JSON."""

    def build_prompt(self, diff_text: str) -> str:
        return f"""Analyze the following code for performance issues.

CHECK FOR THESE SPECIFIC ISSUES:
1. **O(n^2) or worse algorithms**: Nested loops over the same data, repeated linear searches
2. **N+1 query problem**: Database queries inside loops (should use JOIN or batch fetch)
3. **Memory inefficiency**: Loading entire files into memory, large string concatenation in loops
4. **Blocking in async context**: Using time.sleep(), synchronous I/O in async functions
5. **Missing memoization**: Recursive functions without caching (e.g., naive fibonacci)
6. **Inefficient data structures**: Using lists for lookups instead of sets/dicts
7. **Repeated computation**: Same expensive calculation done multiple times in a loop

SEVERITY GUIDELINES:
- **critical**: Will cause outages or timeouts at production scale (e.g., N+1 with 10K rows)
- **high**: Significant slowdown, O(n^2) or worse on user-facing paths
- **medium**: Noticeable inefficiency, wasted resources (e.g., loading whole file for line count)
- **low**: Minor optimization opportunity, style preference

CODE TO ANALYZE:
```
{diff_text}
```

Respond with a JSON object in this EXACT format:
{{
    "findings": [
        {{
            "title": "Short title of the performance issue",
            "severity": "critical|high|medium|low",
            "description": "What the issue is, why it's slow, and what the complexity is",
            "file_path": "filename if identifiable",
            "line_number": null,
            "suggestion": "Specific fix with example code approach",
            "confidence": 0.9
        }}
    ]
}}

If no performance issues are found, return: {{"findings": []}}"""
