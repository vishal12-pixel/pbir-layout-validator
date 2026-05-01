"""Extract the user-facing title (display name) from a Visual's raw JSON.

The title lives in
``raw["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"]``
as a Power BI string literal — wrapped in single quotes (e.g.
``'Net Seat Adds by Partner and Fiscal Time'``). Some visuals (action
buttons, pivot tables, slicers) have no title at all; in that case the
function returns an empty string and callers should fall back to the
``visual_type``.

This module is stdlib-only (no third-party imports).
"""

from __future__ import annotations

from typing import Any

from .models import Visual


def _unwrap_literal(value: Any) -> str:
    """Strip the surrounding single quotes from a PBI string literal.

    The serialized form is ``"'My Title'"``. Doubled single-quotes inside a
    literal escape one literal quote (``"'It''s'"`` → ``It's``).
    """
    if not isinstance(value, str) or len(value) < 2:
        return ""
    if value.startswith("'") and value.endswith("'"):
        inner = value[1:-1]
        return inner.replace("''", "'")
    return value


def extract_title(visual: Visual) -> str:
    """Return the visual's display title, or an empty string if absent."""
    raw = visual.raw
    if not isinstance(raw, dict):
        return ""

    container = raw.get("visualContainerObjects")
    if not isinstance(container, dict):
        return ""

    title_entries = container.get("title")
    if not isinstance(title_entries, list) or not title_entries:
        return ""

    first = title_entries[0]
    if not isinstance(first, dict):
        return ""

    props = first.get("properties")
    if not isinstance(props, dict):
        return ""

    text = props.get("text")
    if not isinstance(text, dict):
        return ""

    expr = text.get("expr")
    if not isinstance(expr, dict):
        return ""

    literal = expr.get("Literal")
    if not isinstance(literal, dict):
        return ""

    value = literal.get("Value")
    return _unwrap_literal(value)


def row_title(visuals: tuple[Visual, ...]) -> str:
    """Join unique titles of a row's visuals, comma-separated.

    Empty if no visual in the row has a title.
    """
    seen: list[str] = []
    for v in visuals:
        title = extract_title(v).strip()
        if title and title not in seen:
            seen.append(title)
    return ", ".join(seen)
