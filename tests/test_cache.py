from app.core.cache import request_hash


def test_request_hash_is_stable_for_same_messages() -> None:
    messages = [{"role": "user", "content": "Explain polymorphism."}]

    assert request_hash(messages) == request_hash(messages)


def test_request_hash_changes_when_content_changes() -> None:
    first = [{"role": "user", "content": "Explain polymorphism."}]
    second = [{"role": "user", "content": "Explain inheritance."}]

    assert request_hash(first) != request_hash(second)
