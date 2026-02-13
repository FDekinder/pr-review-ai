"""
Test all 5 agents independently against sample code.
Verifies each agent works before wiring them into the orchestrator.
"""

import asyncio
import sys
import time

sys.path.insert(0, ".")

from backend.agents.security_agent import SecurityAgent
from backend.agents.performance_agent import PerformanceAgent
from backend.agents.testing_agent import TestingAgent
from backend.agents.documentation_agent import DocumentationAgent
from backend.agents.standards_agent import StandardsAgent
from backend.models.ollama_client import OllamaClient


async def test_agent(agent, code, label):
    """Run a single agent and print results."""
    print(f"\n{'-' * 60}")
    print(f"  {label}")
    print(f"{'-' * 60}")

    result = await agent.analyze(code)

    print(f"  Status: {result.status.value} | Model: {result.model_used} | Time: {result.execution_time}s")
    print(f"  Findings: {len(result.findings)}")

    for i, f in enumerate(result.findings, 1):
        print(f"  [{i}] [{f.severity.value.upper():8s}] {f.title}")
        print(f"      {f.description[:100]}...")
        if f.suggestion:
            print(f"      Fix: {f.suggestion[:80]}...")

    if result.error:
        print(f"  ERROR: {result.error}")

    return result


async def main():
    client = OllamaClient()

    # Read all sample files
    with open("sample_prs/security_issues.py") as f:
        security_code = f.read()
    with open("sample_prs/performance_problems.py") as f:
        performance_code = f.read()
    with open("sample_prs/missing_tests.py") as f:
        testing_code = f.read()

    print("=" * 60)
    print("  All Agents Test — Running 5 agents sequentially")
    print("=" * 60)

    total_start = time.time()

    # Test each agent against its relevant sample code
    agents_tests = [
        (SecurityAgent(ollama_client=client), security_code, "SECURITY AGENT vs security_issues.py"),
        (PerformanceAgent(ollama_client=client), performance_code, "PERFORMANCE AGENT vs performance_problems.py"),
        (TestingAgent(ollama_client=client), testing_code, "TESTING AGENT vs missing_tests.py"),
        (DocumentationAgent(ollama_client=client), testing_code, "DOCUMENTATION AGENT vs missing_tests.py"),
        (StandardsAgent(ollama_client=client), performance_code, "STANDARDS AGENT vs performance_problems.py"),
    ]

    results = []
    for agent, code, label in agents_tests:
        result = await test_agent(agent, code, label)
        results.append((label.split(" vs ")[0].strip(), result))

    total_time = time.time() - total_start

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY — Sequential execution")
    print(f"{'=' * 60}")
    total_findings = 0
    for name, result in results:
        status = "OK" if result.status.value == "completed" else "FAIL"
        count = len(result.findings)
        total_findings += count
        print(f"  [{status}] {name:30s} {count} findings in {result.execution_time}s")

    print(f"\n  Total findings: {total_findings}")
    print(f"  Total time (sequential): {total_time:.1f}s")
    print(f"  With parallel execution, this would be ~{max(r.execution_time for _, r in results):.1f}s")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
