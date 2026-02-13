"""
End-to-end test: LangGraph orchestrator running all 5 agents in parallel.

This is the moment of truth — does the full multi-agent pipeline work?

Expected behavior:
1. Orchestrator receives code with mixed issues
2. Fans out to 5 agents simultaneously
3. Each agent finds issues in its specialty
4. Results are aggregated into one AnalysisResult
5. Total time should be ~max(agent times), NOT sum
"""

import asyncio
import sys
import time

sys.path.insert(0, ".")

from backend.agents.orchestrator import PRReviewOrchestrator
from backend.models.ollama_client import OllamaClient


# Code with problems spanning ALL agent specialties
MIXED_ISSUES_CODE = '''
import os
import pickle
import time

# Security: SQL injection + hardcoded secret
API_KEY = "sk-secret-12345"

def get_user(username):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    return db.execute(query)

# Performance: O(n^2) + blocking in async
def find_duplicates(items):
    duplicates = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i] == items[j]:
                duplicates.append(items[i])
    return duplicates

async def process_batch(items):
    for item in items:
        time.sleep(1)  # blocks the event loop!
        await save(item)

# Testing: complex branching with no tests
def process_order(order):
    if order.get("status") == "cancelled":
        refund(order)
        return "refunded"
    elif order.get("total", 0) > 1000:
        if order.get("member"):
            apply_discount(order)
            return "discounted"
        else:
            require_approval(order)
            return "pending"
    else:
        charge(order)
        return "completed"

# Documentation: no docstrings anywhere
# Standards: inconsistent naming, magic numbers
def calcTotal(x, y, z):
    return x * 1.08 + y * 0.95 - z * 0.1
'''


async def main():
    client = OllamaClient()
    orchestrator = PRReviewOrchestrator(ollama_client=client)

    print("=" * 60)
    print("  LangGraph Orchestrator - Full Multi-Agent Test")
    print("=" * 60)
    print(f"\n  Running 5 agents in PARALLEL via LangGraph...")
    print(f"  Agents: security, performance, testing, documentation, standards\n")

    start = time.time()
    result = await orchestrator.run(MIXED_ISSUES_CODE)
    total = time.time() - start

    # Display results by agent
    print(f"\n{'=' * 60}")
    print(f"  RESULTS")
    print(f"{'=' * 60}")

    for ar in result.agent_results:
        status = "OK" if ar.status.value == "completed" else "FAIL"
        print(f"\n  [{status}] {ar.agent.value.upper()} AGENT ({ar.model_used}) - {ar.execution_time}s")
        for f in ar.findings:
            print(f"    [{f.severity.value.upper():8s}] {f.title}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total findings: {result.total_findings}")
    print(f"    Critical: {result.critical_count}")
    print(f"    High:     {result.high_count}")
    print(f"    Medium:   {result.medium_count}")
    print(f"    Low:      {result.low_count}")
    print(f"")
    print(f"  Agents completed: {len(result.agent_results)}/5")
    print(f"  Slowest agent:    {result.total_execution_time}s")
    print(f"  Wall clock time:  {total:.1f}s")

    # Compare parallel vs sequential
    sequential_time = sum(ar.execution_time for ar in result.agent_results)
    speedup = sequential_time / total if total > 0 else 0
    print(f"  Sequential would be: {sequential_time:.1f}s")
    print(f"  Parallel speedup:   {speedup:.1f}x faster")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
