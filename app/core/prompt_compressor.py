from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompressionResult:
    messages: list[dict[str, str]]
    compressed: bool
    original_words: int
    compressed_words: int
    compression_ratio: float | None
    reason: str


def word_count(text: str) -> int:
    return len(text.split())


def normalize_messages(messages: list[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for message in messages:
        if isinstance(message, dict):
            role = str(message["role"])
            content = str(message["content"])
        else:
            role = str(message.role)
            content = str(message.content)
        normalized.append({"role": role, "content": content})
    return normalized


def total_words(messages: list[Any]) -> int:
    return sum(word_count(message["content"]) for message in normalize_messages(messages))


def should_compress(messages: list[Any], word_threshold: int = 600) -> bool:
    return total_words(messages) > word_threshold


def compress_text_preserving_edges(text: str, target_words: int) -> str:
    words = text.split()
    target_words = max(12, target_words)
    if len(words) <= target_words:
        return text

    marker_word_count = 4
    body_budget = max(2, target_words - marker_word_count)
    head_count = max(1, body_budget // 2)
    tail_count = max(1, body_budget - head_count)

    if head_count + tail_count >= len(words):
        return text

    omitted_count = len(words) - head_count - tail_count
    marker = f"[compressed {omitted_count} words omitted]"
    return " ".join([*words[:head_count], marker, *words[-tail_count:]])


def compress_messages(
    messages: list[Any],
    *,
    enabled: bool = True,
    word_threshold: int = 600,
    target_words: int = 350,
) -> CompressionResult:
    normalized = normalize_messages(messages)
    original_words = total_words(normalized)

    if not enabled:
        return CompressionResult(
            messages=normalized,
            compressed=False,
            original_words=original_words,
            compressed_words=original_words,
            compression_ratio=None,
            reason="prompt compression disabled",
        )

    if original_words <= word_threshold:
        return CompressionResult(
            messages=normalized,
            compressed=False,
            original_words=original_words,
            compressed_words=original_words,
            compression_ratio=None,
            reason=f"prompt compression skipped; words={original_words}",
        )

    system_words = sum(
        word_count(message["content"])
        for message in normalized
        if message["role"] == "system"
    )
    compressible_messages = [
        message for message in normalized if message["role"] != "system"
    ]
    compressible_words = sum(word_count(message["content"]) for message in compressible_messages)
    target_for_compressible = max(12, target_words - system_words)

    compressed_messages: list[dict[str, str]] = []
    for message in normalized:
        if message["role"] == "system" or compressible_words == 0:
            compressed_messages.append(message)
            continue

        message_words = word_count(message["content"])
        message_budget = max(
            12,
            round(target_for_compressible * (message_words / compressible_words)),
        )
        compressed_messages.append(
            {
                "role": message["role"],
                "content": compress_text_preserving_edges(
                    message["content"],
                    target_words=message_budget,
                ),
            }
        )

    compressed_words = total_words(compressed_messages)
    compressed = compressed_words < original_words
    compression_ratio = None
    if compressed and original_words:
        compression_ratio = round(compressed_words / original_words, 4)

    reason = (
        f"prompt compressed {original_words}->{compressed_words} words"
        if compressed
        else f"prompt compression skipped; words={original_words}"
    )
    return CompressionResult(
        messages=compressed_messages,
        compressed=compressed,
        original_words=original_words,
        compressed_words=compressed_words,
        compression_ratio=compression_ratio,
        reason=reason,
    )
