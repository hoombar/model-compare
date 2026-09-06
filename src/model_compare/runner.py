"""Async runner for parallel OpenRouter chat completion calls."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass
class ModelResult:
    alias: str
    slug: str
    content: str | None = None
    error: str | None = None
    latency_s: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost: float | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.content is not None


def _extract_error(payload: dict) -> str:
    err = payload.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err)
    if err is not None:
        return str(err)
    return str(payload)[:300]


async def run_model(
    client: httpx.AsyncClient,
    api_key: str,
    alias: str,
    slug: str,
    system_prompt: str,
    user_prompt: str,
    timeout: float,
) -> ModelResult:
    """Call one model; errors are captured on the result, never raised."""
    result = ModelResult(alias=alias, slug=slug)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": "model-compare",
    }
    body = {
        "model": slug,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "usage": {"include": True},
    }
    start = time.perf_counter()
    try:
        resp = await client.post(OPENROUTER_URL, headers=headers, json=body, timeout=timeout)
        result.latency_s = time.perf_counter() - start
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        if resp.status_code != 200:
            result.error = f"HTTP {resp.status_code}: {_extract_error(payload)}"
            return result
        choices = payload.get("choices") or []
        content = ((choices[0].get("message") or {}).get("content")) if choices else None
        if not content:
            result.error = "empty response"
            return result
        result.content = content
        usage = payload.get("usage") or {}
        result.prompt_tokens = usage.get("prompt_tokens")
        result.completion_tokens = usage.get("completion_tokens")
        result.cost = usage.get("cost")
    except (TimeoutError, httpx.HTTPError) as exc:
        result.latency_s = time.perf_counter() - start
        result.error = f"{type(exc).__name__}: {exc}"
    return result


async def run_all(
    pairs: list[tuple[str, str]],
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    timeout: float,
) -> list[ModelResult]:
    """Run every model in parallel, preserving input order."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(
                run_model(
                    client,
                    api_key,
                    alias,
                    slug,
                    system_prompt,
                    user_prompt,
                    timeout,
                )
                for alias, slug in pairs
            )
        )
    return list(results)
