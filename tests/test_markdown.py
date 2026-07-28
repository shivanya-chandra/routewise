from app.core.markdown import render_markdown
from app.schemas import RouteResponse


def test_markdown_renders_headings_bold_and_lists() -> None:
    rendered = render_markdown(
        "## Benefits\n\n1. **Fast** cache hits\n2. Lower model cost"
    )

    assert "<h2>Benefits</h2>" in rendered
    assert "<ol>" in rendered
    assert "<strong>Fast</strong>" in rendered


def test_markdown_removes_unsafe_html() -> None:
    rendered = render_markdown(
        '<script>alert("unsafe")</script><img src=x onerror=alert(1)>\n\n**Safe**'
    )

    assert "<script" not in rendered
    assert "<img" not in rendered
    assert "onerror" not in rendered
    assert "<strong>Safe</strong>" in rendered


def test_route_response_includes_sanitized_answer_html() -> None:
    response = RouteResponse(
        request_id="request-id",
        answer="- **Cached** result",
        selected_model="cache",
        final_model="cache",
        cache_hit=True,
        fallback_count=0,
        route_reason="exact cache hit",
    )

    dumped = response.model_dump()

    assert dumped["answer_html"] == "<ul>\n<li><strong>Cached</strong> result</li>\n</ul>"
