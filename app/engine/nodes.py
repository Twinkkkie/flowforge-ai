from typing import Any

import httpx
from openai import AsyncOpenAI

from app.core.config import settings
from app.engine.context import get_path, render_value


async def run_transform(config: dict, context: dict) -> dict:
    values = render_value(config.get("set", {}), context)
    return {"values": values}


async def run_condition(config: dict, context: dict) -> dict:
    actual = get_path(context, config.get("path", ""))
    expected = render_value(config.get("value"), context)
    operator = config.get("operator", "eq")

    if operator == "eq":
        matched = actual == expected
    elif operator == "ne":
        matched = actual != expected
    elif operator == "gt":
        matched = actual > expected
    elif operator == "gte":
        matched = actual >= expected
    elif operator == "lt":
        matched = actual < expected
    elif operator == "lte":
        matched = actual <= expected
    elif operator == "contains":
        matched = expected in actual if actual is not None else False
    else:
        raise ValueError(f"Unsupported condition operator: {operator}")

    return {"matched": matched, "branch": "true" if matched else "false"}


async def run_http(config: dict, context: dict) -> dict:
    method = str(config.get("method", "GET")).upper()
    url = render_value(config.get("url", ""), context)
    if not url:
        raise ValueError("HTTP node requires url")

    headers = render_value(config.get("headers", {}), context)
    body = render_value(config.get("json"), context)

    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        response = await client.request(method, url, headers=headers, json=body)
        response.raise_for_status()

    try:
        payload: Any = response.json()
    except ValueError:
        payload = response.text

    return {"status_code": response.status_code, "body": payload}


async def run_ai(config: dict, context: dict) -> dict:
    prompt = render_value(config.get("prompt", ""), context)
    if not prompt:
        raise ValueError("AI node requires prompt")

    if not settings.openai_api_key:
        return {
            "mode": "offline",
            "content": f"AI node skipped external call. Rendered prompt: {prompt}",
        }

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.responses.create(
        model=settings.openai_model,
        instructions=str(config.get("system", "Return a concise useful result.")),
        input=str(prompt),
    )
    return {"mode": "openai", "content": response.output_text}


NODE_HANDLERS = {
    "transform": run_transform,
    "condition": run_condition,
    "http": run_http,
    "ai": run_ai,
}
