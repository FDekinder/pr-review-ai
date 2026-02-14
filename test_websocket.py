"""
Test the WebSocket endpoint end-to-end.

This script:
1. Connects to ws://localhost:8000/ws/analyze
2. Sends a code snippet with known issues
3. Prints each real-time event as it arrives
4. Shows the final analysis result

RUN:
    1. Start the backend: venv/Scripts/python -m uvicorn backend.api.main:app --reload
    2. Run this test:     venv/Scripts/python test_websocket.py
"""

import asyncio
import json
import sys

sys.path.insert(0, ".")


async def main():
    # websockets library is needed for standalone WS client
    try:
        import websockets
    except ImportError:
        print("Installing websockets library...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
        import websockets

    test_code = '''
import os

API_KEY = "sk-secret-12345"

def get_user(username):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    return db.execute(query)

def find_duplicates(items):
    duplicates = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i] == items[j]:
                duplicates.append(items[i])
    return duplicates

def calcTotal(x, y, z):
    return x * 1.08 + y * 0.95 - z * 0.1
'''

    uri = "ws://localhost:8000/ws/analyze"
    print("=" * 60)
    print("  WebSocket End-to-End Test")
    print("=" * 60)
    print(f"\n  Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as ws:
            print("  Connected! Sending code for analysis...\n")

            # Send the analysis request
            await ws.send(json.dumps({"diff_text": test_code}))

            # Receive events until the connection closes
            event_count = 0
            async for message in ws:
                event = json.loads(message)
                event_count += 1
                event_type = event.get("event_type", "unknown")
                agent = event.get("agent", "")
                msg = event.get("message", "")

                # Color-code events
                if event_type == "error":
                    prefix = "  [ERROR]"
                elif event_type.endswith("_completed"):
                    prefix = "  [DONE] "
                elif event_type.endswith("_started"):
                    prefix = "  [START]"
                else:
                    prefix = "  [EVENT]"

                agent_str = f" ({agent})" if agent else ""
                print(f"{prefix}{agent_str} {msg}")

                # Print summary from final result
                if event_type == "analysis_completed" and event.get("data"):
                    data = event["data"]
                    print(f"\n  {'=' * 50}")
                    print(f"  FINAL RESULT")
                    print(f"  {'=' * 50}")
                    print(f"  Total findings: {data.get('total_findings', '?')}")
                    print(f"    Critical: {data.get('critical_count', '?')}")
                    print(f"    High:     {data.get('high_count', '?')}")
                    print(f"    Medium:   {data.get('medium_count', '?')}")
                    print(f"    Low:      {data.get('low_count', '?')}")
                    print(f"  Time:  {data.get('total_execution_time', '?')}s")

            print(f"\n  Connection closed. Received {event_count} events.")
            print("  WebSocket test PASSED!")

    except ConnectionRefusedError:
        print("\n  ERROR: Could not connect to the backend.")
        print("  Make sure the server is running:")
        print("    venv/Scripts/python -m uvicorn backend.api.main:app --reload")
    except Exception as e:
        print(f"\n  ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(main())
