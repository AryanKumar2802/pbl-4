
"""OpenRouter API client for making LLM requests."""

import asyncio
import httpx
from typing import List, Dict, Any, Optional

from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL


# Request configuration
MAX_RETRIES = 2
RETRY_DELAY = 3.0
DEFAULT_TIMEOUT = 75.0

RETRYABLE_STATUS_CODES = {
    408, 429, 500, 502, 503, 504
}


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = DEFAULT_TIMEOUT
) -> Optional[Dict[str, Any]]:

    if not OPENROUTER_API_KEY:
        print("[CONFIG ERROR] OPENROUTER_API_KEY is missing.")
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://pbl-4-lwdo.onrender.com",
        "X-Title": "LLM Council",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=15.0)
            ) as client:

                response = await client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload
                )

                if response.status_code != 200:

                    print(
                        f"[HTTP ERROR] Model: {model} | "
                        f"Status: {response.status_code}"
                    )

                    print(
                        f"[HTTP ERROR] Response: "
                        f"{response.text[:1000]}"
                    )

                    if (
                        response.status_code in RETRYABLE_STATUS_CODES
                        and attempt < MAX_RETRIES
                    ):
                        wait = RETRY_DELAY * attempt

                        print(
                            f"[RETRY] {model} in {wait} seconds "
                            f"(attempt {attempt + 1}/{MAX_RETRIES})"
                        )

                        await asyncio.sleep(wait)
                        continue

                    return None

                data = response.json()

                if "error" in data:
                    print(
                        f"[API ERROR] Model: {model} | "
                        f"Details: {data['error']}"
                    )
                    return None

                choices = data.get("choices", [])

                if not choices:
                    print(
                        f"[EMPTY RESPONSE] Model: {model} "
                        "returned no choices."
                    )
                    return None

                message = choices[0].get("message", {})
                content = message.get("content", "")

                if not content:
                    print(
                        f"[EMPTY CONTENT] Model: {model}"
                    )
                    return None

                print(f"[SUCCESS] Model responded: {model}")

                return {
                    "content": content,
                    "reasoning_details": message.get(
                        "reasoning_details"
                    ),
                }

        except httpx.TimeoutException:
            print(
                f"[TIMEOUT] {model} | "
                f"Attempt {attempt}/{MAX_RETRIES}"
            )

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue

            return None

        except httpx.RequestError as error:
            print(
                f"[CONNECTION ERROR] {model}: "
                f"{type(error).__name__}: {error}"
            )

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue

            return None

        except Exception as error:
            print(
                f"[UNEXPECTED ERROR] {model}: "
                f"{type(error).__name__}: {error}"
            )
            return None

    return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:

    print(
        f"\n[PARALLEL QUERY] Starting {len(models)} model requests"
    )

    tasks = [
        query_model(model, messages)
        for model in models
    ]

    responses = await asyncio.gather(
        *tasks,
        return_exceptions=True
    )

    results = {}

    for model, response in zip(models, responses):

        if isinstance(response, Exception):
            print(
                f"[PARALLEL ERROR] {model}: {response}"
            )
            results[model] = None

        else:
            results[model] = response

    succeeded = [
        model for model, response in results.items()
        if response is not None
    ]

    failed = [
        model for model, response in results.items()
        if response is None
    ]

    print("\n[PARALLEL QUERY SUMMARY]")
    print(f"Successful models: {len(succeeded)}/{len(models)}")

    for model in succeeded:
        print(f"  [OK] {model}")

    for model in failed:
        print(f"  [FAILED] {model}")

    return results
