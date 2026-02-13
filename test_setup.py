"""
Phase 1.1 Setup Verification Script

Run this after installing Ollama and pulling models to verify everything works.

Usage:
    python test_setup.py

This script will:
1. Check Ollama connection
2. List available models
3. Test a simple generation
4. Test JSON-formatted output (critical for agents)
5. Compare speed between models (if multiple are available)
"""

import asyncio
import sys
import time

# Add the project root to Python path so imports work
sys.path.insert(0, ".")

from backend.models.ollama_client import OllamaClient
from backend.config import settings


async def main():
    client = OllamaClient()

    print("=" * 60)
    print("PR Review AI - Setup Verification")
    print("=" * 60)

    # ----------------------------------------------------------
    # Step 1: Check Ollama Connection
    # ----------------------------------------------------------
    print("\n[1/5] Checking Ollama connection...")
    try:
        await client.check_connection()
        print("  OK - Ollama is running!")
    except ConnectionError as e:
        print(f"  FAIL - {e}")
        print("\n  Please install Ollama from https://ollama.com/download")
        print("  Then make sure it's running (it should start automatically)")
        await client.close()
        return

    # ----------------------------------------------------------
    # Step 2: List Available Models
    # ----------------------------------------------------------
    print("\n[2/5] Checking available models...")
    models = await client.list_models()

    if not models:
        print("  No models found! Pull models with:")
        print(f"    ollama pull {settings.fast_model}")
        print(f"    ollama pull {settings.balanced_model}")
        await client.close()
        return

    print(f"  Found {len(models)} model(s):")
    for model in models:
        name = model["name"]
        size_gb = model.get("size", 0) / (1024 ** 3)
        print(f"    - {name} ({size_gb:.1f} GB)")

    # Check which of our required models are available
    required_models = [settings.fast_model, settings.balanced_model]
    available = []
    for model_name in required_models:
        is_available = await client.check_model_available(model_name)
        status = "READY" if is_available else "MISSING"
        print(f"  {model_name}: {status}")
        if is_available:
            available.append(model_name)

    if not available:
        print("\n  No required models found! Pull at least one:")
        for m in required_models:
            print(f"    ollama pull {m}")
        await client.close()
        return

    # Use the first available model for testing
    test_model = available[0]

    # ----------------------------------------------------------
    # Step 3: Test Simple Generation
    # ----------------------------------------------------------
    print(f"\n[3/5] Testing text generation with {test_model}...")
    print("  (First call may be slow as the model loads into memory)")

    result = await client.generate(
        model=test_model,
        prompt="What is a SQL injection vulnerability? Answer in 2 sentences.",
    )

    print(f"  Response ({result['elapsed_seconds']}s):")
    print(f"  {result['response'][:300]}")

    # ----------------------------------------------------------
    # Step 4: Test JSON Generation (Critical for Agents)
    # ----------------------------------------------------------
    print(f"\n[4/5] Testing JSON generation with {test_model}...")
    print("  This is how our agents will return structured findings.")

    json_result = await client.generate_json(
        model=test_model,
        prompt="""Analyze this Python code for security issues:

```python
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    cursor.execute(query)
    return cursor.fetchone()
```

Return a JSON object with:
- "issues": array of objects, each with "title", "severity" (low/medium/high/critical), "description"
""",
        system_prompt="You are a code security analyzer. Always respond with valid JSON.",
    )

    import json
    print(f"  Response ({json_result['elapsed_seconds']}s):")
    print(f"  {json.dumps(json_result['data'], indent=2)[:500]}")

    # ----------------------------------------------------------
    # Step 5: Speed Comparison (if multiple models available)
    # ----------------------------------------------------------
    if len(available) > 1:
        print(f"\n[5/5] Speed comparison between models...")
        test_prompt = "List 3 common Python security vulnerabilities. Be brief."

        for model_name in available:
            start = time.time()
            result = await client.generate(model=model_name, prompt=test_prompt)
            elapsed = time.time() - start
            tokens = result.get("eval_count", "?")
            print(f"  {model_name}: {elapsed:.1f}s ({tokens} tokens)")
    else:
        print(f"\n[5/5] Skipping speed comparison (only 1 model available)")
        print(f"  Pull more models to compare: ollama pull {settings.balanced_model}")

    # ----------------------------------------------------------
    # Summary
    # ----------------------------------------------------------
    print("\n" + "=" * 60)
    print("Setup Verification Complete!")
    print("=" * 60)
    print(f"\nModels ready: {', '.join(available)}")
    print("Next step: Phase 1.2 - Building the Security Agent")
    print("\nRun with: python -m pytest tests/ -v")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
