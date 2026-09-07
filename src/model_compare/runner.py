"""Async runner for parallel OpenRouter chat completion calls."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Awaitable, Callable
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
    on_result: Callable[[ModelResult], Awaitable[None]] | None = None,
) -> list[ModelResult]:
    """Run every model in parallel, preserving input order.

    `on_result` fires as each model completes (completion order, not input order).
    """
    async with httpx.AsyncClient() as client:
        tasks = [
            asyncio.create_task(
                run_model(client, api_key, alias, slug, system_prompt, user_prompt, timeout)
            )
            for alias, slug in pairs
        ]
        if on_result is not None:
            for task in asyncio.as_completed(tasks):
                result = await task
                await on_result(result)
        else:
            results = await asyncio.gather(*tasks)
            return list(results)
        return [task.result() for task in tasks]


async def _run_with_progress(
    pairs: list[tuple[str, str]],
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    timeout: float,
    total: int,
) -> list[ModelResult]:
    """Run all models with a live progress line; log each result as it lands."""
    done = 0
    lock = asyncio.Lock()

    async def report(result: ModelResult) -> None:
        nonlocal done
        async with lock:
            done += 1
            if result.ok:
                status = f"done    {result.latency_s:6.1f}s  {result.completion_tokens} tok"
            else:
                status = "ERROR"
            sys.stdout.write(f"\r\033[K  [{done:>2}/{total}] {result.alias}: {status}\n")
            elapsed = time.monotonic() - t0
            sys.stdout.write(
                f"  waiting... {int(elapsed // 60):02d}:{int(elapsed % 60):02d} elapsed"
            )
            sys.stdout.flush()

    async def ticker() -> None:
        while True:
            elapsed = time.monotonic() - t0
            sys.stdout.write(
                f"\r\033[K  waiting... {int(elapsed // 60):02d}:{int(elapsed % 60):02d} elapsed"
            )
            sys.stdout.flush()
            await asyncio.sleep(1)

    t0 = time.monotonic()
    sys.stdout.write("  waiting... 00:00 elapsed")
    sys.stdout.flush()
    tick_task = asyncio.create_task(ticker())
    try:
        results = await run_all(
            pairs, system_prompt, user_prompt, api_key, timeout, on_result=report
        )
    finally:
        tick_task.cancel()
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()
    return results
