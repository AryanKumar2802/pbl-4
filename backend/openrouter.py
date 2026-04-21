"""OpenRouter API client for making LLM requests."""

import httpx
import asyncio
from typing import List, Dict, Any, Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL
print("🔑 KEY BEING USED:", repr(OPENROUTER_API_KEY[:20]))

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 5.0  # seconds between retries on rate limit


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5173",
        "X-Title": "LLM Council Prototype",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload
                )

                # Log full response body before raising so we always see the error
                if response.status_code != 200:
                    print(f"[HTTP ERROR] Model: {model}")
                    print(f"[HTTP ERROR] Status: {response.status_code}")
                    print(f"[HTTP ERROR] Body: {response.text}")

                response.raise_for_status()

                data = response.json()

                # Check for API-level errors returned with 200 status
                if "error" in data:
                    print(f"[API ERROR] Model: {model}")
                    print(f"[API ERROR] Details: {data['error']}")
                    return None

                choices = data.get("choices", [])

                if not choices:
                    print(f"[EMPTY RESPONSE] Model: {model} returned no choices")
                    print(f"[EMPTY RESPONSE] Full response: {data}")
                    return None

                message = choices[0].get("message", {})
                content = message.get("content", "")

                if not content:
                    print(f"[EMPTY CONTENT] Model: {model} returned empty content")
                    return None

                return {
                    "content": content,
                    "reasoning_details": message.get("reasoning_details"),
                }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                print(f"[Rate Limit] Model: {model} — attempt {attempt}/{MAX_RETRIES}")
                print(f"[Rate Limit] Response: {e.response.text}")
                if attempt < MAX_RETRIES:
                    wait = RETRY_DELAY * attempt  # exponential-ish backoff
                    print(f"[Rate Limit] Waiting {wait}s before retry...")
                    await asyncio.sleep(wait)
                    continue
                else:
                    print(f"[Rate Limit] Max retries reached for {model}")
                    return None
            else:
                print(f"[HTTP ERROR] Model: {model} — Status: {e.response.status_code}")
                print(f"[HTTP ERROR] Body: {e.response.text}")
                return None

        except httpx.TimeoutException:
            print(f"[TIMEOUT] Model: {model} timed out after {timeout}s (attempt {attempt}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return None

        except Exception as e:
            print(f"[UNEXPECTED ERROR] Model: {model}")
            print(f"[UNEXPECTED ERROR] Type: {type(e).__name__}")
            print(f"[UNEXPECTED ERROR] Details: {str(e)}")
            return None

    return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:

    tasks = [query_model(model, messages) for model in models]
    responses = await asyncio.gather(*tasks, return_exceptions=False)

    results = {model: response for model, response in zip(models, responses)}

    # Log summary of which models succeeded/failed
    succeeded = [m for m, r in results.items() if r is not None]
    failed = [m for m, r in results.items() if r is None]

    if succeeded:
        print(f"[Parallel Query] Succeeded: {succeeded}")
    if failed:
        print(f"[Parallel Query] Failed: {failed}")

    return results