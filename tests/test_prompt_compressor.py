from app.core.prompt_compressor import compress_messages, should_compress
from app.schemas import ChatMessage


def words(count: int) -> str:
    return " ".join(f"word{i}" for i in range(count))


def test_short_prompt_is_not_compressed() -> None:
    messages = [{"role": "user", "content": "hello there"}]

    result = compress_messages(messages, word_threshold=10, target_words=5)

    assert result.compressed is False
    assert result.messages == messages
    assert result.original_words == 2
    assert result.compressed_words == 2
    assert result.compression_ratio is None


def test_long_prompt_is_compressed_preserving_edges() -> None:
    messages = [{"role": "user", "content": words(100)}]

    result = compress_messages(messages, word_threshold=20, target_words=30)

    assert result.compressed is True
    assert result.original_words == 100
    assert result.compressed_words == 30
    assert result.compression_ratio == 0.3
    assert result.messages[0]["content"].startswith("word0 word1")
    assert result.messages[0]["content"].endswith("word98 word99")
    assert "[compressed 74 words omitted]" in result.messages[0]["content"]


def test_system_messages_are_preserved_when_user_prompt_is_compressed() -> None:
    system_content = "You are a careful assistant."
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": words(100)},
    ]

    result = compress_messages(messages, word_threshold=20, target_words=30)

    assert result.compressed is True
    assert result.messages[0]["content"] == system_content
    assert result.messages[1]["content"] != words(100)
    assert result.compressed_words <= 30


def test_compression_can_be_disabled() -> None:
    messages = [{"role": "user", "content": words(100)}]

    result = compress_messages(messages, enabled=False, word_threshold=20, target_words=30)

    assert result.compressed is False
    assert result.messages == messages
    assert result.reason == "prompt compression disabled"


def test_should_compress_accepts_chat_message_objects() -> None:
    messages = [ChatMessage(role="user", content="one two three")]

    assert should_compress(messages, word_threshold=2) is True
