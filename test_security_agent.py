"""
Manual test: Run the SecurityAgent against our sample vulnerable code.

This script lets you see exactly what the agent does:
1. Loads the sample code with known vulnerabilities
2. Passes it to the SecurityAgent
3. Prints each finding with severity, description, and suggestion

Expected findings (6 vulnerabilities in security_issues.py):
1. SQL Injection (Critical) - f-string in SQL query
2. Command Injection (Critical) - os.system with user input
3. Hardcoded Secrets (High) - API key and password in code
4. Insecure Deserialization (High) - pickle.loads on user data
5. Path Traversal (Medium) - unsanitized filename in file path
6. Subprocess shell=True (High) - shell injection risk
"""

import asyncio
import sys

sys.path.insert(0, ".")

from backend.agents.security_agent import SecurityAgent
from backend.models.ollama_client import OllamaClient


async def main():
    # Read the sample vulnerable code
    with open("sample_prs/security_issues.py", "r") as f:
        vulnerable_code = f.read()

    print("=" * 60)
    print("Security Agent Test")
    print("=" * 60)
    print(f"\nAnalyzing sample_prs/security_issues.py...")
    print(f"Code length: {len(vulnerable_code)} characters\n")

    # Create the agent and run analysis
    client = OllamaClient()
    agent = SecurityAgent(ollama_client=client)

    result = await agent.analyze(vulnerable_code)

    # Display results
    print(f"\nStatus: {result.status.value}")
    print(f"Model: {result.model_used}")
    print(f"Time: {result.execution_time}s")
    print(f"Findings: {len(result.findings)}")
    print("-" * 60)

    for i, finding in enumerate(result.findings, 1):
        severity_colors = {
            "critical": "CRITICAL",
            "high": "HIGH    ",
            "medium": "MEDIUM  ",
            "low": "LOW     ",
        }
        severity_label = severity_colors.get(finding.severity.value, "UNKNOWN ")

        print(f"\n[{i}] [{severity_label}] {finding.title}")
        print(f"    Confidence: {finding.confidence}")
        print(f"    {finding.description}")
        if finding.suggestion:
            print(f"    FIX: {finding.suggestion}")

    # Summary
    print("\n" + "=" * 60)
    critical = sum(1 for f in result.findings if f.severity.value == "critical")
    high = sum(1 for f in result.findings if f.severity.value == "high")
    medium = sum(1 for f in result.findings if f.severity.value == "medium")
    low = sum(1 for f in result.findings if f.severity.value == "low")
    print(f"Summary: {critical} Critical, {high} High, {medium} Medium, {low} Low")
    print(f"Total analysis time: {result.execution_time}s")

    if result.error:
        print(f"\nERROR: {result.error}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
