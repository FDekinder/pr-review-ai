"""
SecurityAgent - Detects security vulnerabilities in code changes.

This is the first and most critical agent in our system. It analyzes
code diffs looking for common security vulnerabilities from the OWASP
Top 10 and beyond.

WHAT IT DETECTS:
    - SQL Injection
    - Command Injection / OS Command Injection
    - Cross-Site Scripting (XSS)
    - Hardcoded Secrets (API keys, passwords, tokens)
    - Insecure Deserialization
    - Path Traversal
    - Insecure Subprocess Usage
    - Weak Cryptography
    - Missing Input Validation

WHY qwen2.5-coder:7b?
    Security analysis requires understanding code semantics - not just
    pattern matching. The 7B model is significantly better at reasoning
    about data flow (e.g., "user input flows into SQL query without
    sanitization"). The 3B model would catch obvious patterns but miss
    subtle issues.

PROMPT ENGINEERING NOTES:
    The prompt is carefully structured with:
    1. Clear role definition ("You are a security expert")
    2. Specific categories to check (reduces hallucination)
    3. Required output format (JSON with specific fields)
    4. Examples of what to look for (few-shot guidance)
    5. Severity guidelines (so ratings are consistent)
"""

from backend.agents.base_agent import BaseAgent
from backend.config import settings
from backend.models.schemas import AgentType


class SecurityAgent(BaseAgent):
    """
    Analyzes code diffs for security vulnerabilities.

    Uses the 7B code model for deeper reasoning about
    data flow and security implications.
    """

    agent_type = AgentType.SECURITY
    model = settings.balanced_model  # qwen2.5-coder:7b

    @property
    def system_prompt(self) -> str:
        return """You are an expert code security auditor. Your job is to analyze code changes (diffs) and identify security vulnerabilities.

You have deep knowledge of:
- OWASP Top 10 vulnerabilities
- Language-specific security pitfalls (Python, JavaScript, etc.)
- Secure coding best practices
- Common attack vectors and exploitation techniques

IMPORTANT RULES:
- Only report REAL vulnerabilities you can see in the code. Do NOT hallucinate issues.
- Focus on the code that was ADDED or MODIFIED (lines starting with +).
- Be specific: mention exact function names, variable names, and line patterns.
- Rate severity accurately based on exploitability and impact.

Always respond with valid JSON."""

    def build_prompt(self, diff_text: str) -> str:
        """
        Build the security analysis prompt.

        PROMPT ENGINEERING KEY CONCEPTS:
        1. Be specific about what to look for (reduces hallucination)
        2. Define the output format precisely (makes parsing reliable)
        3. Include severity guidelines (makes ratings consistent)
        4. Tell it what NOT to do (prevents false positives)
        """
        return f"""Analyze the following code for security vulnerabilities.

CHECK FOR THESE SPECIFIC ISSUES:
1. **SQL Injection**: String formatting/concatenation in SQL queries instead of parameterized queries
2. **Command Injection**: User input passed to os.system(), subprocess with shell=True, eval(), exec()
3. **Hardcoded Secrets**: API keys, passwords, tokens, or credentials in source code
4. **Insecure Deserialization**: Use of pickle.loads(), yaml.load() without SafeLoader, eval() on user data
5. **Path Traversal**: User-controlled file paths without sanitization (../../etc/passwd attacks)
6. **XSS**: Unescaped user input rendered in HTML templates
7. **Weak Cryptography**: MD5/SHA1 for passwords, ECB mode, small key sizes
8. **Missing Input Validation**: Functions that trust external input without checking

SEVERITY GUIDELINES:
- **critical**: Directly exploitable, leads to data breach or RCE (e.g., SQL injection, command injection)
- **high**: Serious security flaw, exploitable with some effort (e.g., hardcoded secrets, insecure deserialization)
- **medium**: Security weakness that could be exploited in specific conditions (e.g., path traversal, weak crypto)
- **low**: Minor security concern or best practice violation (e.g., verbose error messages, missing headers)

CODE TO ANALYZE:
```
{diff_text}
```

Respond with a JSON object in this EXACT format:
{{
    "findings": [
        {{
            "title": "Short title of the vulnerability",
            "severity": "critical|high|medium|low",
            "description": "Detailed explanation of the vulnerability and how it could be exploited",
            "file_path": "filename if identifiable from the diff",
            "line_number": null,
            "suggestion": "Specific code fix or mitigation strategy",
            "confidence": 0.9
        }}
    ]
}}

If no security issues are found, return: {{"findings": []}}"""
