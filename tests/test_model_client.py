import asyncio

from app.core.model_client import call_ollama, messages_with_completion_budget


def test_completion_budget_instruction_precedes_messages() -> None:
    messages = [{"role": "user", "content": "Explain routing in five points."}]

    prepared = messages_with_completion_budget(messages, 256)

    assert prepared[0]["role"] == "system"
    assert "no more than 140 words" in prepared[0]["content"]
    assert "within 256 generated tokens" in prepared[0]["content"]
    assert "finish every requested point" in prepared[0]["content"]
    assert prepared[1:] == messages


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
            "done_reason": "length",
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
    assert result.finish_reason == "length"
