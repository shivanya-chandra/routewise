import bleach
from markdown import markdown


ALLOWED_TAGS = {
    "blockquote",
    "br",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}


def render_markdown(value: str) -> str:
    rendered = markdown(
        value,
        extensions=["fenced_code", "sane_lists"],
        output_format="html",
    )
    return bleach.clean(
        rendered,
        tags=ALLOWED_TAGS,
        attributes={},
        strip=True,
    )
