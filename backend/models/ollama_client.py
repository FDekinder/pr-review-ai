"""
Ollama Client - Wrapper for the local LLM API.

WHY a wrapper instead of calling Ollama directly?
1. Centralized error handling - if Ollama is down, one place to handle it
2. Logging - track which models are called, how long they take
3. Abstraction - if we switch from Ollama to another provider, only this file changes
4. Testing - we can mock this class in tests instead of needing a running Ollama

HOW Ollama works under the hood:
- Ollama runs as a background service on port 11434
- When you call /api/generate, it:
  1. Loads the model into RAM/VRAM (first call is slow, subsequent calls are fast)
  2. Tokenizes your prompt (converts text to numbers the model understands)
  3. Runs inference (the model generates tokens one by one)
  4. Returns the response
- Models stay loaded in memory for ~5 minutes after last use, then get unloaded
"""

import json
import time
from typing import Optional

import httpx

from backend.config import settings


class OllamaClient:
    """
    Client for interacting with the Ollama API.

    Usage:
        client = OllamaClient()
        await client.check_connection()
        response = await client.generate("qwen2.5-coder:7b", "Explain this code: ...")
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.ollama_base_url
        # httpx is like 'requests' but supports async
        # timeout is high because first model load can take 30+ seconds
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(120.0),
        )

    async def check_connection(self) -> bool:
        """
        Verify Ollama is running and accessible.

        Returns True if connected, raises an exception with helpful message if not.
        """
        try:
            response = await self.client.get("/api/tags")
            response.raise_for_status()
            return True
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is installed and running. "
                "You can start it with: ollama serve"
            )

    async def list_models(self) -> list[dict]:
        """
        List all models currently downloaded in Ollama.

        This calls GET /api/tags which returns info about each model:
        - name, size, modified date, etc.
        """
        response = await self.client.get("/api/tags")
        response.raise_for_status()
        data = response.json()
        return data.get("models", [])

    async def check_model_available(self, model_name: str) -> bool:
        """Check if a specific model is downloaded."""
        models = await self.list_models()
        available_names = [m["name"] for m in models]
        # Ollama sometimes adds ":latest" suffix, so check both forms
        return model_name in available_names or f"{model_name}:latest" in available_names

    async def generate(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        format_json: bool = False,
    ) -> dict:
        """
        Generate a response from a local LLM.

        Args:
            model: Which model to use (e.g., "qwen2.5-coder:7b")
            prompt: The user's prompt
            system_prompt: Optional system instructions (sets agent "personality")
            temperature: 0.0 = deterministic, 1.0 = creative.
                         We use 0.1 for code analysis because we want consistent,
                         factual responses - not creative fiction.
            format_json: If True, tells the model to respond in valid JSON.
                         This is crucial for parsing agent outputs reliably.

        Returns:
            Dict with 'response' (the text), 'model', 'total_duration', etc.
        """
        start_time = time.time()

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,  # Get complete response at once (streaming comes in Week 3)
            "options": {
                "temperature": temperature,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        if format_json:
            payload["format"] = "json"

        try:
            response = await self.client.post("/api/generate", json=payload)
            response.raise_for_status()
            result = response.json()

            elapsed = time.time() - start_time
            result["elapsed_seconds"] = round(elapsed, 2)

            print(f"[Ollama] Model: {model} | Time: {elapsed:.1f}s | "
                  f"Tokens: {result.get('eval_count', '?')}")

            return result

        except httpx.TimeoutException:
            raise TimeoutError(
                f"Model '{model}' timed out after 120 seconds. "
                "This can happen on first load. Try again - subsequent calls are faster."
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(
                    f"Model '{model}' not found. "
                    f"Pull it with: ollama pull {model}"
                )
            raise

    async def generate_json(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
    ) -> dict:
        """
        Generate a response and parse it as JSON.

        WHY a separate method?
        Agents need structured output (findings as JSON), not free text.
        This method:
        1. Tells Ollama to force JSON output format
        2. Parses the response string into a Python dict
        3. Handles parsing errors gracefully

        This is a common pattern in agentic systems - you need to bridge
        between the LLM's natural language and your code's structured data.
        """
        result = await self.generate(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            format_json=True,
        )

        response_text = result.get("response", "")

        try:
            parsed = json.loads(response_text)
            return {
                "data": parsed,
                "model": model,
                "elapsed_seconds": result.get("elapsed_seconds", 0),
                "eval_count": result.get("eval_count", 0),
            }
        except json.JSONDecodeError as e:
            # LLMs sometimes produce invalid JSON despite being asked for JSON.
            # In production, you'd retry or use a JSON repair library.
            raise ValueError(
                f"Model returned invalid JSON: {e}\n"
                f"Raw response: {response_text[:500]}"
            )

    async def close(self):
        """Clean up the HTTP client."""
        await self.client.aclose()
