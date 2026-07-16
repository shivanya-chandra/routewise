import asyncio
import json
import urllib.request
from dataclasses import dataclass
from typing import Any

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


async def call_ollama(model: str, messages: list[dict[str, str]]) -> ModelResult:
    ollama_model = ollama_model_name(model)
    if ollama_model is None:
        raise ValueError(f"Not an Ollama model: {model}")

    base_url = settings.ollama_base_url.rstrip("/")
    payload = {
        "model": ollama_model,
        "messages": messages,
        "stream": False,
    }

    data = await asyncio.to_thread(post_ollama_chat, f"{base_url}/api/chat", payload)
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


def post_ollama_chat(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout_seconds = settings.ollama_http_timeout_seconds

    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        response_body = response.read().decode("utf-8")

    return json.loads(response_body)


def get_ollama_tags(url: str, timeout_seconds: float) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")

    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        response_body = response.read().decode("utf-8")

    return json.loads(response_body)


async def list_ollama_models(timeout_seconds: float | None = None) -> list[str]:
    base_url = settings.ollama_base_url.rstrip("/")
    timeout = timeout_seconds or settings.ollama_http_timeout_seconds
    data = await asyncio.to_thread(get_ollama_tags, f"{base_url}/api/tags", timeout)

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


async def call_model(model: str, messages: list[dict[str, str]]) -> ModelResult:
    if ollama_model_name(model) is not None:
        return await call_ollama(model, messages)

    from litellm import acompletion

    response = await acompletion(model=model, messages=messages)
    answer = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)

    return ModelResult(
        answer=answer,
        prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
        completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        total_tokens=getattr(usage, "total_tokens", None) if usage else None,
        raw=response,
    )
