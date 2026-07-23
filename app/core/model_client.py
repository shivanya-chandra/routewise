import asyncio
import importlib
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


@dataclass(frozen=True)
class ModelResult:
    answer: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    raw: Any


def ollama_model_name(model: str) -> str | None:
    if not model.startswith("ollama/"):
        return None
    return model.split("/", 1)[1]


async def call_ollama(
    model: str,
    messages: list[dict[str, str]],
    max_completion_tokens: int | None = None,
) -> ModelResult:
    ollama_model = ollama_model_name(model)
    if ollama_model is None:
        raise ValueError(f"Not an Ollama model: {model}")

    base_url = settings.ollama_base_url.rstrip("/")
    payload = {
        "model": ollama_model,
        "messages": messages,
        "stream": False,
        "keep_alive": settings.ollama_keep_alive,
        "options": {
            "num_predict": (
                max_completion_tokens or settings.preflight_default_completion_tokens
            ),
            "num_ctx": settings.ollama_context_length,
        },
    }

    data = await post_ollama_chat(
        f"{base_url}/api/chat",
        payload,
        timeout_seconds=settings.ollama_http_timeout_seconds,
    )
    answer = data.get("message", {}).get("content") or ""
    prompt_tokens = data.get("prompt_eval_count")
    completion_tokens = data.get("eval_count")
    total_tokens = None
    if prompt_tokens is not None or completion_tokens is not None:
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

    return ModelResult(
        answer=answer,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        raw=data,
    )


async def post_ollama_chat(
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


async def get_ollama_tags(url: str, timeout_seconds: float) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def list_ollama_models(timeout_seconds: float | None = None) -> list[str]:
    base_url = settings.ollama_base_url.rstrip("/")
    timeout = timeout_seconds or settings.ollama_http_timeout_seconds
    data = await get_ollama_tags(f"{base_url}/api/tags", timeout)

    model_names: list[str] = []
    for model in data.get("models", []):
        name = model.get("name") or model.get("model")
        if name:
            model_names.append(str(name))

    return model_names


def ollama_model_available(model: str, available_models: list[str]) -> bool:
    ollama_model = ollama_model_name(model)
    if ollama_model is None:
        return False

    available = set(available_models)
    return (
        ollama_model in available
        or f"{ollama_model}:latest" in available
        or any(name.split(":", 1)[0] == ollama_model for name in available)
    )


async def call_model(
    model: str,
    messages: list[dict[str, str]],
    max_completion_tokens: int | None = None,
) -> ModelResult:
    if ollama_model_name(model) is not None:
        return await call_ollama(model, messages, max_completion_tokens)

    litellm = await asyncio.to_thread(importlib.import_module, "litellm")

    response = await litellm.acompletion(
        model=model,
        messages=messages,
        max_tokens=max_completion_tokens or settings.preflight_default_completion_tokens,
    )
    answer = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)

    return ModelResult(
        answer=answer,
        prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
        completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        total_tokens=getattr(usage, "total_tokens", None) if usage else None,
        raw=response,
    )
