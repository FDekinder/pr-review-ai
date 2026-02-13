"""
Quick script to test the API endpoints.

Run the server first:
    venv/Scripts/python -m uvicorn backend.api.main:app --port 8000

Then run this:
    venv/Scripts/python test_api.py
"""

import httpx
import json
import asyncio


API_BASE = "http://localhost:8000"


async def main():
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Test 1: Root
        print("=" * 60)
        print("[1] GET / - Root endpoint")
        r = await client.get(f"{API_BASE}/")
        print(f"  Status: {r.status_code}")
        print(f"  Response: {r.json()}")

        # Test 2: Health
        print("\n[2] GET /api/health - Health check")
        r = await client.get(f"{API_BASE}/api/health")
        health = r.json()
        print(f"  Status: {r.status_code}")
        print(f"  Ollama: {'connected' if health['ollama_connected'] else 'NOT connected'}")
        print(f"  Models: {health['models_available']}")
        print(f"  Agents: {health['agents_ready']}")

        # Test 3: Analyze vulnerable code
        print("\n[3] POST /api/analyze - Analyze vulnerable code")
        print("  Sending code with SQL injection + hardcoded secret...")

        vulnerable_code = '''
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    cursor.execute(query)
    return cursor.fetchone()

API_KEY = "sk-secret-key-12345"

def run_command(user_input):
    import os
    os.system(f"echo {user_input}")
'''

        r = await client.post(
            f"{API_BASE}/api/analyze",
            json={"diff_text": vulnerable_code},
        )
        result = r.json()
        print(f"  Status: {r.status_code}")
        print(f"  Analysis ID: {result['id']}")
        print(f"  Total findings: {result['total_findings']}")
        print(f"  Time: {result['total_execution_time']}s")
        print(f"  Breakdown: {result['critical_count']} Critical, "
              f"{result['high_count']} High, "
              f"{result['medium_count']} Medium, "
              f"{result['low_count']} Low")

        print("\n  Findings:")
        for i, agent_result in enumerate(result['agent_results']):
            print(f"\n  [{agent_result['agent']}] - {agent_result['status']}")
            for f in agent_result['findings']:
                print(f"    [{f['severity'].upper():8s}] {f['title']}")
                if f['suggestion']:
                    print(f"             Fix: {f['suggestion'][:80]}...")

        # Test 4: Retrieve by ID
        analysis_id = result['id']
        print(f"\n[4] GET /api/analysis/{analysis_id} - Retrieve by ID")
        r = await client.get(f"{API_BASE}/api/analysis/{analysis_id}")
        print(f"  Status: {r.status_code}")
        print(f"  Found: {r.json()['total_findings']} findings (same as before)")

        # Test 5: History
        print("\n[5] GET /api/history - Analysis history")
        r = await client.get(f"{API_BASE}/api/history")
        history = r.json()
        print(f"  Status: {r.status_code}")
        print(f"  Total analyses: {history['count']}")

        # Test 6: Error case - no input
        print("\n[6] POST /api/analyze - Error: no input")
        r = await client.post(f"{API_BASE}/api/analyze", json={})
        print(f"  Status: {r.status_code} (expected 400)")
        print(f"  Error: {r.json()['detail']}")

        # Test 7: Not found
        print("\n[7] GET /api/analysis/nonexistent - Error: not found")
        r = await client.get(f"{API_BASE}/api/analysis/nonexistent")
        print(f"  Status: {r.status_code} (expected 404)")
        print(f"  Error: {r.json()['detail']}")

        print("\n" + "=" * 60)
        print("All API tests complete!")
        print(f"Swagger docs available at: {API_BASE}/docs")


if __name__ == "__main__":
    asyncio.run(main())
