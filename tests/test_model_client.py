import asyncio

from app.core.model_client import call_ollama


def test_call_ollama_sends_answer_limit_and_keep_alive(monkeypatch) -> None:
    captured: dict = {}

    async def fake_post(url, payload, timeout_seconds):
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout_seconds"] = timeout_seconds
        return {
            "message": {"content": "Hello!"},
            "prompt_eval_count": 8,
            "eval_count": 3,
        }

    monkeypatch.setattr("app.core.model_client.post_ollama_chat", fake_post)
    monkeypatch.setattr("app.core.model_client.settings.ollama_keep_alive", "30m")
    monkeypatch.setattr("app.core.model_client.settings.ollama_context_length", 2048)

    result = asyncio.run(
        call_ollama(
            "ollama/llama3.2",
            [{"role": "user", "content": "Say hello."}],
            max_completion_tokens=32,
        )
    )

    assert captured["url"].endswith("/api/chat")
    assert captured["payload"]["keep_alive"] == "30m"
    assert captured["payload"]["options"]["num_predict"] == 32
    assert captured["payload"]["options"]["num_ctx"] == 2048
    assert result.answer == "Hello!"
    assert result.total_tokens == 11
